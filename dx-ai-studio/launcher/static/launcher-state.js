
window.DXLauncher = window.DXLauncher || {};

window.DXLauncher._splashTimers = [];
window.DXLauncher._splashActive = false;
window.DXLauncher._deferredLauncherWorkStarted = false;
window.DXLauncher._launcherCoreStarted = false;
window.DXLauncher._studioReadyPromise = null;
window.DXLauncher._studioReadyResolved = false;

window.DXLauncher.currentApp = null;
window.DXLauncher.APP_PATHS = {
  app: '/app/',
  stream: '/stream/',
  zoo: '/zoo/',
  compiler: '/compiler/',
  planner: '/planner/',
  benchmark: '/benchmark/',
  dx_monitor: '/dx_monitor/',
  agent: '/agent/',
  cloud: '/cloud/',
};

window.DXLauncher._SPLASH_MODULES = [
  { name: 'DX App',       angle: 0,    icon: 'app' },
  { name: 'DX Stream',    angle: 40,   icon: 'stream' },
  { name: 'DX Model Zoo', angle: 80,   icon: 'zoo' },
  { name: 'DX Compiler',  angle: 120,  icon: 'compiler' },
  { name: 'DX EdgeGuide', angle: 160,  icon: 'edgeguide' },
  { name: 'DX Benchmark', angle: 200,  icon: 'benchmark' },
  { name: 'DX Monitor',   angle: 240,  icon: 'monitor' },
  { name: 'DX Agent Dev', angle: 280,  icon: 'agent' },
  { name: 'DX Cloud',     angle: 320,  icon: 'cloud' },
];

window.DXLauncher._DECODE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
window.DXLauncher._DECODE_FRAME_INTERVAL = 50;
window.DXLauncher._TRACE_LENGTH_CACHE = new Map();
window.DXLauncher._decodeRAF = null;

window.DXLauncher._orbitalResizeTimer = null;

window.DXLauncher.SUPPORTED_LANGS = ['en', 'ja', 'ko', 'es', 'zh-CN', 'zh-TW'];
window.DXLauncher.LANG_SHORT = { en: 'EN', ja: 'JA', ko: 'KO', es: 'ES', 'zh-CN': '简', 'zh-TW': '繁' };
