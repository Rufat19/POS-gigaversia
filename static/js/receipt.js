window.printReceipt = function (result, cartSnapshot, receiptWindow) {
  const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]);
  const total = Number(result.total || 0);
  const saleId = escapeHtml(result.sale_id || '');
  const now = new Intl.DateTimeFormat('az-AZ', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(new Date());
  const itemsHtml = cartSnapshot.map(item => `
    <article class="receipt-item">
      <div class="item-name">${escapeHtml(item.name)}</div>
      <div class="item-details">
        <span>${Number(item.quantity)} × ${Number(item.price).toFixed(2)} AZN</span>
        <strong>${(Number(item.price) * Number(item.quantity)).toFixed(2)} AZN</strong>
      </div>
    </article>
  `).join('');
  const html = `
    <!doctype html>
    <html lang="az"><head><meta charset="utf-8"><title>Satış qəbzi</title>
    <style>
      @page{size:80mm auto;margin:0}
      *{box-sizing:border-box}
      html,body{width:80mm;margin:0;padding:0;background:#fff;color:#111}
      body{font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.4}
      .receipt{width:80mm;padding:4mm 4mm 5mm;margin:0 auto}
      .brand{text-align:center;padding-bottom:10px;border-bottom:1px dashed #555}
      .brand-name{font-size:24px;font-weight:900;letter-spacing:1px}
      .brand-subtitle{margin-top:2px;font-size:10px;color:#444}
      .receipt-title{margin:12px 0 8px;text-align:center;font-size:15px;font-weight:800}
      .meta{display:flex;justify-content:space-between;gap:8px;margin:3px 0;font-size:10px}
      .items{margin-top:12px;border-top:1px dashed #555}
      .receipt-item{padding:8px 0;border-bottom:1px dashed #aaa;break-inside:avoid}
      .item-name{font-weight:700;overflow-wrap:anywhere}
      .item-details{display:flex;justify-content:space-between;gap:8px;margin-top:3px;font-size:11px}
      .item-details strong{white-space:nowrap}
      .total{display:flex;justify-content:space-between;gap:8px;padding:12px 0 10px;font-size:16px;font-weight:800}
      .footer{padding-top:9px;border-top:1px dashed #555;text-align:center;font-size:11px}
      @media screen{body{background:#e5e7eb}.receipt{min-height:100vh;background:#fff;box-shadow:0 2px 16px #0002}}
    </style></head><body>
    <main class="receipt">
      <header class="brand">
        <div class="brand-name">RoBo</div>
        <div class="brand-subtitle">Satış qəbzi</div>
      </header>
      <div class="meta"><span>Satış №</span><strong>${saleId}</strong></div>
      <div class="meta"><span>Tarix</span><span>${escapeHtml(now)}</span></div>
      <section class="items" aria-label="Satılan məhsullar">${itemsHtml}</section>
      <div class="total"><span>YEKUN</span><span>${total.toFixed(2)} AZN</span></div>
      <footer class="footer">Təşəkkür edirik!<br>Yenidən gözləyirik.</footer>
    </main>
    <script>window.addEventListener('load',function(){window.focus();setTimeout(function(){window.print();},500);});<\/script>
    </body></html>
  `;
  receiptWindow.document.write(html);
  receiptWindow.document.close();
};
