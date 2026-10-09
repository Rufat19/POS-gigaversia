package az.robo.pos;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.print.PrintManager;
import android.text.InputType;
import android.view.Gravity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.net.http.SslError;
import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;

public class MainActivity extends ComponentActivity {
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final String PREFERENCES = "robo_pos_settings";
    private static final String SERVER_URL_KEY = "server_url";

    private Uri appUri;
    private String appUrl;
    private WebView mainWebView;
    private WebView popupWebView;
    private Dialog popupDialog;
    private EditText urlInput;
    private TextView setupError;
    private android.webkit.ValueCallback<Uri[]> fileChooserCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (popupDialog != null && popupDialog.isShowing()) {
                    closePopup();
                } else if (mainWebView != null && mainWebView.canGoBack()) {
                    mainWebView.goBack();
                } else {
                    finish();
                }
            }
        });

        String savedUrl = getPreferences(MODE_PRIVATE).getString(SERVER_URL_KEY, null);
        if (savedUrl != null) {
            try {
                appUrl = normalizeServerUrl(savedUrl);
                appUri = Uri.parse(appUrl);
                showPos();
                return;
            } catch (IllegalArgumentException error) {
                showSetup(savedUrl, getString(R.string.invalid_saved_url));
                return;
            }
        }

        showSetup("", null);
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(Menu.NONE, 1, Menu.NONE, getString(R.string.change_server_url))
                .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            showSetup(appUrl == null ? "" : appUrl, null);
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void showSetup(String currentUrl, String initialError) {
        closePopup();
        if (mainWebView != null) {
            mainWebView.stopLoading();
            mainWebView.destroy();
            mainWebView = null;
        }

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        int horizontalPadding = dp(28);
        page.setPadding(horizontalPadding, dp(36), horizontalPadding, dp(24));
        page.setGravity(Gravity.CENTER_VERTICAL);
        page.setBackgroundColor(Color.rgb(243, 246, 251));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(24), dp(26), dp(24), dp(22));
        card.setBackground(new ColorDrawable(Color.WHITE));
        page.addView(card, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = new TextView(this);
        title.setText(R.string.server_title);
        title.setTextColor(Color.rgb(31, 41, 55));
        title.setTextSize(23);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        card.addView(title);

        TextView description = new TextView(this);
        description.setText(R.string.server_description);
        description.setTextColor(Color.rgb(102, 112, 133));
        description.setTextSize(15);
        LinearLayout.LayoutParams descriptionParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        descriptionParams.topMargin = dp(8);
        descriptionParams.bottomMargin = dp(22);
        card.addView(description, descriptionParams);

        TextView label = new TextView(this);
        label.setText(R.string.server_url_label);
        label.setTextColor(Color.rgb(31, 41, 55));
        label.setTextSize(14);
        label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        card.addView(label);

        urlInput = new EditText(this);
        urlInput.setSingleLine(true);
        urlInput.setTextSize(16);
        urlInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        urlInput.setHint(R.string.server_url_hint);
        urlInput.setText(currentUrl);
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(52));
        inputParams.topMargin = dp(8);
        card.addView(urlInput, inputParams);

        Button saveButton = new Button(this);
        saveButton.setText(R.string.save_and_open);
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(50));
        buttonParams.topMargin = dp(12);
        card.addView(saveButton, buttonParams);

        setupError = new TextView(this);
        setupError.setTextColor(Color.rgb(180, 35, 24));
        setupError.setTextSize(13);
        LinearLayout.LayoutParams errorParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        errorParams.topMargin = dp(8);
        card.addView(setupError, errorParams);
        if (initialError != null) setupError.setText(initialError);

        saveButton.setOnClickListener(view -> saveServerUrl());
        setContentView(page);
        urlInput.requestFocus();
        urlInput.setSelection(urlInput.length());
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
    }

    private void saveServerUrl() {
        try {
            appUrl = normalizeServerUrl(urlInput.getText().toString());
            appUri = Uri.parse(appUrl);
            getPreferences(MODE_PRIVATE).edit().putString(SERVER_URL_KEY, appUrl).apply();
            showPos();
        } catch (IllegalArgumentException error) {
            setupError.setText(error.getMessage());
        }
    }

    private String normalizeServerUrl(String value) {
        String candidate = value == null ? "" : value.trim();
        Uri uri = Uri.parse(candidate);
        String scheme = uri.getScheme();
        if (candidate.isEmpty()) {
            throw new IllegalArgumentException(getString(R.string.enter_server_url));
        }
        if (!("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme))
                || uri.getHost() == null
                || uri.getUserInfo() != null) {
            throw new IllegalArgumentException(getString(R.string.invalid_server_url));
        }
        return uri.normalizeScheme().toString();
    }

    private void showPos() {
        mainWebView = createWebView();
        setContentView(mainWebView);
        mainWebView.loadUrl(appUrl);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private WebView createWebView() {
        WebView webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(false);
        settings.setSupportMultipleWindows(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        webView.setWebViewClient(new PosWebViewClient());
        webView.setWebChromeClient(new PosWebChromeClient());
        return webView;
    }

    private boolean isTrustedUrl(Uri destination) {
        if (appUri == null || destination.getHost() == null) return false;
        return appUri.getScheme().equalsIgnoreCase(destination.getScheme())
                && appUri.getHost().equalsIgnoreCase(destination.getHost())
                && effectivePort(appUri) == effectivePort(destination);
    }

    private int effectivePort(Uri uri) {
        if (uri.getPort() != -1) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private void openExternal(String destination) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(destination)));
        } catch (ActivityNotFoundException error) {
            Toast.makeText(this, R.string.no_app_for_link, Toast.LENGTH_LONG).show();
        }
    }

    private void showConnectionError(WebView webView, String message) {
        if (webView != mainWebView || isFinishing()) return;
        new AlertDialog.Builder(this)
                .setTitle(R.string.connection_error_title)
                .setMessage(message)
                .setNegativeButton(R.string.change_server, (dialog, which) ->
                        showSetup(appUrl, null))
                .setPositiveButton(R.string.retry, (dialog, which) ->
                        mainWebView.reload())
                .show();
    }

    private void printWebView(WebView webView) {
        if (webView == null || isFinishing()) return;
        PrintManager printManager = (PrintManager) getSystemService(PRINT_SERVICE);
        if (printManager == null) {
            Toast.makeText(this, R.string.print_unavailable, Toast.LENGTH_LONG).show();
            return;
        }
        String jobName = getString(R.string.receipt_print_job);
        printManager.print(jobName, webView.createPrintDocumentAdapter(jobName), null);
    }

    private void closePopup() {
        if (popupDialog != null) {
            popupDialog.dismiss();
            popupDialog = null;
        }
        if (popupWebView != null) {
            popupWebView.destroy();
            popupWebView = null;
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || fileChooserCallback == null) return;

        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null) {
            ClipData clipData = data.getClipData();
            if (clipData != null) {
                result = new Uri[clipData.getItemCount()];
                for (int index = 0; index < clipData.getItemCount(); index++) {
                    result[index] = clipData.getItemAt(index).getUri();
                }
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }
        fileChooserCallback.onReceiveValue(result);
        fileChooserCallback = null;
    }

    @Override
    protected void onDestroy() {
        closePopup();
        if (mainWebView != null) {
            mainWebView.destroy();
            mainWebView = null;
        }
        super.onDestroy();
    }

    private final class PosWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri destination = request.getUrl();
            if (request.isForMainFrame()
                    && "robo-pos-print".equals(destination.getScheme())) {
                printWebView(view);
                return true;
            }
            if (!request.isForMainFrame() || "about".equals(destination.getScheme())) return false;
            if (isTrustedUrl(destination)) return false;
            openExternal(destination.toString());
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            super.onPageFinished(view, url);
            view.evaluateJavascript(
                    "window.print = function () { window.location.href = 'robo-pos-print://print'; };",
                    null);
        }

        @Override
        public void onReceivedError(
                WebView view, WebResourceRequest request, WebResourceError error) {
            super.onReceivedError(view, request, error);
            if (request.isForMainFrame()) {
                showConnectionError(view, getString(R.string.connection_error_message));
            }
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
            handler.cancel();
            showConnectionError(view, getString(R.string.ssl_error));
        }
    }

    private final class PosWebChromeClient extends WebChromeClient {
        @Override
        public boolean onCreateWindow(
                WebView parent, boolean isDialog, boolean isUserGesture, Message resultMessage) {
            closePopup();
            WebView child = createWebView();
            Dialog dialog = new Dialog(MainActivity.this);
            dialog.setContentView(child);
            Window window = dialog.getWindow();
            if (window != null) {
                window.setLayout(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
            }
            dialog.setOnDismissListener(ignored -> {
                if (popupWebView == child) {
                    popupWebView = null;
                    popupDialog = null;
                    child.destroy();
                }
            });
            popupWebView = child;
            popupDialog = dialog;
            dialog.show();
            WebView.WebViewTransport transport =
                    (WebView.WebViewTransport) resultMessage.obj;
            transport.setWebView(child);
            resultMessage.sendToTarget();
            return true;
        }

        @Override
        public void onCloseWindow(WebView window) {
            if (window == popupWebView) closePopup();
        }

        @Override
        public boolean onShowFileChooser(
                WebView webView,
                android.webkit.ValueCallback<Uri[]> filePathCallback,
                FileChooserParams fileChooserParams) {
            if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
            fileChooserCallback = filePathCallback;
            Intent intent = fileChooserParams.createIntent();
            try {
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                return true;
            } catch (ActivityNotFoundException error) {
                fileChooserCallback.onReceiveValue(null);
                fileChooserCallback = null;
                return true;
            }
        }
    }
}
