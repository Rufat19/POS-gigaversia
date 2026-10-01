(() => {
  const dock = document.getElementById('radio-dock');
  if (!dock) return;

  const audio = document.getElementById('radio-audio');
  const stationName = document.getElementById('radio-station-name');
  const stationSelect = document.getElementById('radio-stations');
  const status = document.getElementById('radio-status');
  const playButton = document.getElementById('radio-play');
  const muteButton = document.getElementById('radio-mute');
  const volumeInput = document.getElementById('radio-volume');
  const settings = document.getElementById('radio-settings');
  const expandButton = document.getElementById('radio-expand');
  const icon = document.getElementById('radio-icon');

  const translations = {
    az: {
      label: 'RoBo Radio', loading: 'Stansiyalar yüklənir...', ready: 'Radio hazırdır.',
      play: 'Radionu başlat', pause: 'Radionu dayandır', mute: 'Səsi kəs', unmute: 'Səsi aç',
      previous: 'Əvvəlki stansiya', next: 'Növbəti stansiya', expand: 'Radio ayarlarını aç',
      collapse: 'Radio ayarlarını bağla', stationSelect: 'Radio stansiyası', volume: 'Səs səviyyəsi',
      autoplayBlocked: 'Avtomatik başlama bloklandı — Play düyməsinə basın.',
      unavailable: 'Stansiya qoşulmadı — başqa stansiyanı seçin.',
      listUnavailable: 'Radio siyahısı yüklənmədi. İnternet bağlantısını yoxlayın.',
      noStations: 'Uyğun stansiya tapılmadı.'
    },
    en: {
      label: 'RoBo Radio', loading: 'Loading stations...', ready: 'Radio is ready.',
      play: 'Play radio', pause: 'Pause radio', mute: 'Mute', unmute: 'Unmute',
      previous: 'Previous station', next: 'Next station', expand: 'Open radio settings',
      collapse: 'Close radio settings', stationSelect: 'Radio station', volume: 'Volume',
      autoplayBlocked: 'Autoplay was blocked — press Play.',
      unavailable: 'Station could not connect — choose another station.',
      listUnavailable: 'Could not load stations. Check your internet connection.',
      noStations: 'No compatible stations found.'
    },
    ru: {
      label: 'RoBo Radio', loading: 'Загрузка станций...', ready: 'Радио готово.',
      play: 'Включить радио', pause: 'Остановить радио', mute: 'Выключить звук', unmute: 'Включить звук',
      previous: 'Предыдущая станция', next: 'Следующая станция', expand: 'Открыть настройки радио',
      collapse: 'Закрыть настройки радио', stationSelect: 'Радиостанция', volume: 'Громкость',
      autoplayBlocked: 'Автозапуск заблокирован — нажмите Play.',
      unavailable: 'Станция недоступна — выберите другую.',
      listUnavailable: 'Не удалось загрузить станции. Проверьте интернет.',
      noStations: 'Подходящие станции не найдены.'
    },
    tr: {
      label: 'RoBo Radio', loading: 'Radyolar yükleniyor...', ready: 'Radyo hazır.',
      play: 'Radyoyu başlat', pause: 'Radyoyu durdur', mute: 'Sesi kapat', unmute: 'Sesi aç',
      previous: 'Önceki radyo', next: 'Sonraki radyo', expand: 'Radyo ayarlarını aç',
      collapse: 'Radyo ayarlarını kapat', stationSelect: 'Radyo istasyonu', volume: 'Ses seviyesi',
      autoplayBlocked: 'Otomatik başlatma engellendi — Play düğmesine basın.',
      unavailable: 'İstasyona bağlanılamadı — başka bir istasyon seçin.',
      listUnavailable: 'İstasyonlar yüklenemedi. İnternet bağlantısını kontrol edin.',
      noStations: 'Uygun istasyon bulunamadı.'
    }
  };

  const storage = {
    get(key, fallback) {
      try {
        return localStorage.getItem(`robo_radio_${key}`) ?? fallback;
      } catch (error) {
        console.warn('Radio preference could not be read:', error);
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(`robo_radio_${key}`, String(value));
      } catch (error) {
        console.warn('Radio preference could not be saved:', error);
      }
    }
  };

  let currentLanguage = 'az';
  let stations = [];

  function t(key) {
    return (translations[currentLanguage] || translations.az)[key];
  }

  function applyLabels() {
    const pageLanguage = document.documentElement.lang;
    currentLanguage = translations[pageLanguage] ? pageLanguage : 'az';
    dock.setAttribute('aria-label', t('label'));
    dock.querySelector('[data-radio-label]').textContent = t('label');
    dock.querySelectorAll('[data-radio-title]').forEach(button => {
      const key = button.dataset.radioTitle;
      const label = key === 'play' ? (audio.paused ? t('play') : t('pause'))
        : key === 'mute' ? (audio.muted ? t('unmute') : t('mute'))
          : t(key);
      button.title = label;
      button.setAttribute('aria-label', label);
    });
    stationSelect.setAttribute('aria-label', t('stationSelect'));
    volumeInput.setAttribute('aria-label', t('volume'));
    const expanded = !settings.hidden;
    expandButton.title = t(expanded ? 'collapse' : 'expand');
    expandButton.setAttribute('aria-label', expandButton.title);
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function getSafeStreamUrl(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || !url.hostname || url.hostname === 'localhost' || url.hostname.endsWith('.local')) {
        return null;
      }
      return url.href;
    } catch {
      return null;
    }
  }

  async function fetchStations(tag) {
    const endpoint = new URL('https://de1.api.radio-browser.info/json/stations/search');
    endpoint.searchParams.set('tag', tag);
    endpoint.searchParams.set('limit', '30');
    endpoint.searchParams.set('order', 'votes');
    endpoint.searchParams.set('reverse', 'true');
    endpoint.searchParams.set('hidebroken', 'true');
    endpoint.searchParams.set('codec', 'MP3');
    const response = await fetch(endpoint, {headers: {Accept: 'application/json'}});
    if (!response.ok) throw new Error(`Station directory returned ${response.status}`);
    const result = await response.json();
    if (!Array.isArray(result)) throw new Error('Invalid station directory response');
    return result;
  }

  function normalizeStations(results) {
    const seen = new Set();
    return results.flat().filter(station => {
      if (!station || typeof station !== 'object') return false;
      const streamUrl = getSafeStreamUrl(station.url_resolved || station.url);
      if (
        !streamUrl ||
        typeof station.stationuuid !== 'string' ||
        typeof station.name !== 'string' ||
        seen.has(station.stationuuid)
      ) return false;
      seen.add(station.stationuuid);
      station.url_resolved = streamUrl;
      return true;
    }).slice(0, 30);
  }

  function readStationCache() {
    try {
      const cached = JSON.parse(storage.get('station_directory', 'null'));
      const fetchedAt = Number(storage.get('station_directory_at', '0'));
      if (!Array.isArray(cached) || !Number.isFinite(fetchedAt)) return null;
      const cachedStations = normalizeStations([cached]);
      return cachedStations.length ? {stations: cachedStations, fetchedAt} : null;
    } catch (error) {
      console.warn('Cached radio stations could not be read:', error);
      return null;
    }
  }

  async function loadStationDirectory() {
    const cached = readStationCache();
    if (cached && Date.now() - cached.fetchedAt < 6 * 60 * 60 * 1000) {
      return cached.stations;
    }
    try {
      const results = await Promise.all([
        fetchStations('jazz'),
        fetchStations('lounge'),
        fetchStations('instrumental')
      ]);
      const freshStations = normalizeStations(results);
      if (freshStations.length) {
        storage.set('station_directory', JSON.stringify(freshStations));
        storage.set('station_directory_at', Date.now());
        return freshStations;
      }
      if (cached) return cached.stations;
      return [];
    } catch (error) {
      if (cached) {
        console.warn('Using cached radio stations after directory failure:', error);
        return cached.stations;
      }
      throw error;
    }
  }

  function fillStationSelect() {
    stationSelect.replaceChildren();
    stations.forEach((station, index) => {
      const option = document.createElement('option');
      option.value = station.stationuuid;
      option.textContent = [station.name, station.country].filter(Boolean).join(' · ');
      stationSelect.append(option);
      if (station.stationuuid === storage.get('station', '')) {
        stationSelect.value = station.stationuuid;
      }
      if (index === 0 && !stationSelect.value) stationSelect.value = station.stationuuid;
    });
  }

  function selectStation(station, shouldPlay) {
    if (!station) return;
    const streamUrl = getSafeStreamUrl(station.url_resolved || station.url);
    if (!streamUrl) {
      setStatus(t('unavailable'));
      return;
    }
    storage.set('station', station.stationuuid);
    stationSelect.value = station.stationuuid;
    stationName.textContent = station.name;
    stationName.title = station.name;
    audio.src = streamUrl;
    audio.load();
    setStatus('');
    if (shouldPlay) playRadio();
  }

  async function playRadio() {
    if (!audio.src && stations.length) {
      const station = stations.find(item => item.stationuuid === stationSelect.value) || stations[0];
      selectStation(station, false);
    }
    if (!audio.src) return;
    storage.set('autoplay', 'true');
    try {
      await audio.play();
      setStatus('');
    } catch (error) {
      if (error.name === 'NotAllowedError') setStatus(t('autoplayBlocked'));
      else {
        console.warn('Radio playback could not start:', error);
        setStatus(t('unavailable'));
      }
    }
  }

  function stepStation(step) {
    if (!stations.length) return;
    const currentIndex = stations.findIndex(item => item.stationuuid === stationSelect.value);
    const nextIndex = (currentIndex + step + stations.length) % stations.length;
    selectStation(stations[nextIndex], true);
  }

  function restoreVolume() {
    const savedVolume = Number(storage.get('volume', '20'));
    const volume = Number.isFinite(savedVolume) ? Math.min(100, Math.max(0, savedVolume)) : 20;
    volumeInput.value = String(volume);
    audio.volume = volume / 100;
    audio.muted = storage.get('muted', 'false') === 'true';
    muteButton.textContent = audio.muted ? '◌' : '◖';
    applyLabels();
  }

  document.getElementById('radio-play').addEventListener('click', () => {
    if (audio.paused) playRadio();
    else {
      storage.set('autoplay', 'false');
      audio.pause();
    }
  });
  document.getElementById('radio-previous').addEventListener('click', () => stepStation(-1));
  document.getElementById('radio-next').addEventListener('click', () => stepStation(1));
  muteButton.addEventListener('click', () => {
    audio.muted = !audio.muted;
    storage.set('muted', audio.muted);
    muteButton.textContent = audio.muted ? '◌' : '◖';
    applyLabels();
  });
  stationSelect.addEventListener('change', () => {
    const station = stations.find(item => item.stationuuid === stationSelect.value);
    selectStation(station, true);
  });
  volumeInput.addEventListener('input', () => {
    audio.volume = Number(volumeInput.value) / 100;
    storage.set('volume', volumeInput.value);
  });
  expandButton.addEventListener('click', () => {
    settings.hidden = !settings.hidden;
    expandButton.textContent = settings.hidden ? '⌄' : '⌃';
    expandButton.setAttribute('aria-expanded', String(!settings.hidden));
    applyLabels();
  });
  audio.addEventListener('playing', () => {
    dock.setAttribute('aria-busy', 'false');
    icon.classList.add('is-playing');
    playButton.textContent = 'Ⅱ';
    applyLabels();
  });
  audio.addEventListener('pause', () => {
    icon.classList.remove('is-playing');
    playButton.textContent = '▶';
    applyLabels();
  });
  audio.addEventListener('waiting', () => dock.setAttribute('aria-busy', 'true'));
  audio.addEventListener('error', () => {
    dock.setAttribute('aria-busy', 'false');
    icon.classList.remove('is-playing');
    setStatus(t('unavailable'));
  });
  document.addEventListener('change', event => {
    if (event.target.matches('.lang-select')) setTimeout(applyLabels, 0);
  });

  restoreVolume();
  setStatus(t('loading'));
  loadStationDirectory()
    .then(result => {
      stations = result;
      if (!stations.length) {
        setStatus(t('noStations'));
        dock.setAttribute('aria-busy', 'false');
        return;
      }
      fillStationSelect();
      const selected = stations.find(item => item.stationuuid === stationSelect.value) || stations[0];
      selectStation(selected, false);
      if (storage.get('autoplay', 'true') === 'true') playRadio();
      else setStatus(t('ready'));
      applyLabels();
    })
    .catch(error => {
      console.error('Radio station list could not be loaded:', error);
      setStatus(t('listUnavailable'));
      dock.setAttribute('aria-busy', 'false');
    });
})();
