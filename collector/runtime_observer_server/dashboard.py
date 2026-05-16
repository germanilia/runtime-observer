from __future__ import annotations


DASHBOARD_HTML = r'''
<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Runtime Observer</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
[data-theme="dark"]{--bg:#0a0e14;--bg-subtle:#0f1520;--surface:#131d2b;--surface-raised:#182233;--border:#1e2d3d;--border-subtle:#162030;--text:#e8f0f7;--text-muted:#7a9bb5;--text-subtle:#4a6a85;--primary:#3b82f6;--primary-hover:#2563eb;--primary-muted:rgba(59,130,246,.15);--green:#22c55e;--green-muted:rgba(34,197,94,.15);--yellow:#f59e0b;--yellow-muted:rgba(245,158,11,.15);--red:#ef4444;--red-muted:rgba(239,68,68,.15);--blue:#60a5fa;--blue-muted:rgba(96,165,250,.15);--shadow:0 4px 24px rgba(0,0,0,.4)}
[data-theme="light"]{--bg:#f8fafc;--bg-subtle:#f1f5f9;--surface:#ffffff;--surface-raised:#f8fafc;--border:#e2e8f0;--border-subtle:#f1f5f9;--text:#0f172a;--text-muted:#64748b;--text-subtle:#94a3b8;--primary:#3b82f6;--primary-hover:#2563eb;--primary-muted:rgba(59,130,246,.1);--green:#16a34a;--green-muted:rgba(22,163,74,.1);--yellow:#d97706;--yellow-muted:rgba(217,119,6,.1);--red:#dc2626;--red-muted:rgba(220,38,38,.1);--blue:#2563eb;--blue-muted:rgba(37,99,235,.1);--shadow:0 4px 24px rgba(0,0,0,.08)}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100vh;overflow:hidden}
body{background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5}
body.loading,body.loading *{cursor:wait!important}
#app-shell{height:100vh;display:flex;flex-direction:column;overflow:hidden}
/* TOPBAR */
.topbar{height:56px;flex:none;display:flex;align-items:center;gap:12px;padding:0 16px;background:var(--surface);border-bottom:1px solid var(--border);z-index:20;position:relative}
.topbar-brand{display:flex;align-items:center;gap:10px;flex:none}
.brand-icon{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--primary),#7c3aed);display:flex;align-items:center;justify-content:center;flex:none}
.brand-icon svg{color:#fff}
.brand-name{font-size:15px;font-weight:700;letter-spacing:-.3px;color:var(--text)}
.topbar-divider{width:1px;height:24px;background:var(--border);flex:none}
.topbar-project{font-size:13px;font-weight:500;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:8px}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);flex:none}
.live-text{font-size:12px;color:var(--text-muted)}
.icon-btn{background:none;border:1px solid var(--border);border-radius:6px;padding:5px;cursor:pointer;color:var(--text-muted);display:flex;align-items:center;justify-content:center;transition:border-color .15s,color .15s}
.icon-btn:hover{border-color:var(--primary);color:var(--text)}
.select-sm{background:var(--surface-raised);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 8px;font:inherit;font-size:12px;cursor:pointer}
.select-sm:hover{border-color:var(--primary)}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;font:inherit;font-size:13px;font-weight:500;cursor:pointer;border:1px solid var(--border);background:var(--surface-raised);color:var(--text);transition:border-color .15s,background .15s}
.btn:hover{border-color:var(--primary);background:var(--primary-muted)}
.btn-primary{background:var(--primary);border-color:var(--primary);color:#fff}
.btn-primary:hover{background:var(--primary-hover);border-color:var(--primary-hover)}
.btn-danger{border-color:var(--red-muted);color:var(--red)}
.btn-danger:hover{background:var(--red-muted);border-color:var(--red)}
.env-badge{font-size:11px;font-weight:600;letter-spacing:.04em;padding:2px 7px;border-radius:4px;border:1px solid var(--border);color:var(--text-muted);background:var(--bg-subtle)}
/* BODY AREA */
.body-area{flex:1;overflow:hidden;display:flex;flex-direction:column}
/* PROJECT SCREEN */
#projectScreen{flex:1;overflow-y:auto;padding:24px}
.project-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;max-width:1100px;margin:0 auto}
.project-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;display:flex;flex-direction:column;gap:12px}
.project-card:hover{border-color:var(--primary)}
.project-card-header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.project-name{font-size:16px;font-weight:600}
.project-meta{font-size:12px;color:var(--text-muted)}
.project-actions{display:flex;gap:8px;flex-wrap:wrap}
.project-screen-header{max-width:1100px;margin:0 auto 20px}
.project-screen-title{font-size:22px;font-weight:700;color:var(--text);margin-bottom:4px}
.project-screen-sub{font-size:13px;color:var(--text-muted)}
.empty-projects{text-align:center;padding:60px 24px;color:var(--text-muted);max-width:480px;margin:0 auto}
.empty-projects p{margin-bottom:16px}
/* DASHBOARD SHELL */
#dashboardShell{flex:1;overflow:hidden;display:grid;grid-template-columns:280px minmax(0,1fr)}
/* SIDEBAR */
.sidebar{border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;background:var(--surface)}
.sidebar-apps{padding:10px 10px 0;border-bottom:1px solid var(--border);display:flex;flex-wrap:wrap;gap:4px;flex:none}
.app-tab{padding:5px 10px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;border:1px solid transparent;color:var(--text-muted);background:none;white-space:nowrap;transition:all .15s}
.app-tab:hover{color:var(--text);background:var(--surface-raised)}
.app-tab.active{color:var(--primary);background:var(--primary-muted);border-color:var(--primary)}
.sidebar-search{padding:10px;border-bottom:1px solid var(--border);flex:none}
.search-wrap{position:relative;display:flex;align-items:center}
.search-icon{position:absolute;left:9px;color:var(--text-subtle);pointer-events:none}
.search-input{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:7px 9px 7px 32px;font:inherit;font-size:13px;color:var(--text)}
.search-input::placeholder{color:var(--text-subtle)}
.search-input:focus{outline:none;border-color:var(--primary)}
.sidebar-filter{padding:6px 10px;border-bottom:1px solid var(--border);flex:none}
.filter-toggle{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;font:inherit;font-size:12px;font-weight:500;cursor:pointer;border:1px solid var(--border);background:none;color:var(--text-muted);transition:all .15s;width:100%}
.filter-toggle:hover{background:var(--surface-raised);color:var(--text)}
.filter-toggle.active{background:var(--yellow-muted);border-color:var(--yellow);color:var(--yellow)}
.sidebar-routes{flex:1;overflow-y:auto;padding:6px}
/* ROUTE ITEMS */
.route-item{width:100%;text-align:left;background:none;border:1px solid transparent;border-radius:8px;padding:9px 10px;cursor:pointer;color:var(--text);display:flex;align-items:center;gap:6px;transition:background .1s,border-color .1s;position:relative}
.route-item:hover{background:var(--surface-raised);border-color:var(--border)}
.route-item.active{background:var(--primary-muted);border-color:var(--primary)}
.route-item.hidden-route{opacity:.45}
.route-item-body{flex:1;min-width:0}
.route-top{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.route-path{font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px}
.route-meta{font-size:11px;color:var(--text-muted);display:flex;gap:4px}
.route-item-actions{opacity:0;flex:none;transition:opacity .15s}
.route-item:hover .route-item-actions{opacity:1}
/* METHOD BADGES */
.method-badge{font-size:10px;font-weight:700;letter-spacing:.04em;padding:2px 6px;border-radius:4px;flex:none}
.method-GET{background:var(--green-muted);color:var(--green)}
.method-POST{background:var(--blue-muted);color:var(--blue)}
.method-PUT,.method-PATCH{background:var(--yellow-muted);color:var(--yellow)}
.method-DELETE{background:var(--red-muted);color:var(--red)}
.method-OTHER{background:var(--primary-muted);color:var(--primary)}
/* MAIN CONTENT */
.main-content{display:flex;flex-direction:column;overflow:hidden}
.tab-bar{flex:none;border-bottom:1px solid var(--border);padding:0 16px;display:flex;align-items:center;gap:2px;background:var(--surface)}
.tab-btn{padding:12px 14px;border:none;background:none;color:var(--text-muted);font:inherit;font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;display:flex;align-items:center;gap:6px;transition:color .15s}
.tab-btn:hover{color:var(--text)}
.tab-btn.active{color:var(--primary);border-bottom-color:var(--primary)}
.tab-count{font-size:11px;padding:1px 6px;border-radius:99px;background:var(--surface-raised);color:var(--text-muted)}
.tab-btn.active .tab-count{background:var(--primary-muted);color:var(--primary)}
.tab-panels{flex:1;overflow:hidden;position:relative}
.tab-panel{position:absolute;inset:0;overflow-y:auto;padding:16px;display:none}
.tab-panel.active{display:block}
/* KPI CARDS */
.kpi-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:16px}
.kpi-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.kpi-num{font-size:26px;font-weight:800;line-height:1.1;color:var(--text)}
.kpi-label{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);margin-top:4px}
/* CONTENT CARDS */
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:14px}
.card-header{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:8px}
.card-title{font-size:13px;font-weight:600;color:var(--text)}
.card-body{padding:14px 16px;min-width:0;overflow-wrap:anywhere}
/* BARS */
.bar-row{display:grid;grid-template-columns:minmax(80px,160px) 1fr 60px;gap:10px;align-items:center;padding:4px 0}
.bar-label{font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-muted)}
.bar-track{height:6px;border-radius:99px;background:var(--bg);overflow:hidden}
.bar-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--primary),var(--blue));min-width:4px}
.bar-fill.err{background:linear-gradient(90deg,var(--red),var(--yellow))}
.bar-val{font-size:12px;font-weight:600;text-align:right;color:var(--text-muted)}
/* OVERVIEW GRID */
.overview-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(280px,.7fr);gap:14px}
.insight-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}
.insight-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.insight-title{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
.insight-value{font-size:20px;font-weight:800;margin-top:3px}
.spark{height:38px;display:flex;align-items:end;gap:2px;margin-top:8px}
.spark-bar{flex:1;min-width:3px;border-radius:3px 3px 0 0;background:linear-gradient(180deg,var(--primary),var(--blue));opacity:.85}
.spark-bar.err{background:linear-gradient(180deg,var(--red),var(--yellow))}
.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:8px}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--text)}
/* REQUESTS SPLIT */
.requests-split{display:grid;grid-template-columns:260px minmax(0,1fr);gap:12px;height:100%}
.trace-list{height:100%;overflow-y:auto;display:flex;flex-direction:column;gap:4px}
.trace-item{width:100%;text-align:left;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;color:var(--text);transition:border-color .1s}
.trace-item:hover{border-color:var(--primary)}
.trace-item.active{border-color:var(--primary);background:var(--primary-muted)}
.trace-status{width:8px;height:8px;border-radius:50%;flex:none;margin-top:1px}
.trace-status.ok{background:var(--green)}
.trace-status.err{background:var(--red)}
.trace-header{display:flex;align-items:flex-start;gap:8px;margin-bottom:3px}
.trace-info{min-width:0;flex:1}
.trace-code{font-size:12px;font-weight:700}
.trace-route{font-size:12px;font-weight:500;color:var(--text-muted);overflow-wrap:anywhere;word-break:break-word}
.trace-meta{font-size:11px;color:var(--text-subtle)}
.trace-ms{font-size:12px;font-weight:600;flex:none}
.requests-detail{overflow-y:auto}
.empty-state{border:1px dashed var(--border);border-radius:10px;padding:32px;text-align:center;color:var(--text-muted)}
/* LOGS */
.log-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.log-toolbar .search-wrap{flex:1;min-width:200px}
.log-item{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;margin-bottom:6px;transition:border-color .1s}
.log-item:hover{border-color:var(--primary)}
.log-header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}
.log-body{font-size:13px;margin-bottom:4px;overflow-wrap:anywhere}
.log-footer{display:flex;align-items:center;justify-content:space-between;gap:8px}
.level-badge{font-size:10px;font-weight:700;letter-spacing:.04em;padding:2px 7px;border-radius:4px}
.level-ERROR,.level-CRITICAL{background:var(--red-muted);color:var(--red)}
.level-WARNING{background:var(--yellow-muted);color:var(--yellow)}
.level-INFO{background:var(--blue-muted);color:var(--blue)}
.level-DEBUG{background:var(--surface-raised);color:var(--text-muted)}
/* ERRORS */
.error-item{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px;cursor:pointer;margin-bottom:6px;transition:border-color .1s;text-align:left;width:100%}
.error-item:hover{border-color:var(--red)}
.error-header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}
.error-type{font-size:13px;font-weight:600;color:var(--text)}
.error-msg{font-size:13px;color:var(--text-muted);margin-bottom:4px}
.error-meta{font-size:11px;color:var(--text-subtle)}
/* DEPENDENCIES */
.dep-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;cursor:pointer;margin-bottom:6px;transition:border-color .1s;min-width:0;overflow-wrap:anywhere}
.dep-card:hover{border-color:var(--green)}
.dep-header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px;min-width:0}
.dep-name{font-size:13px;font-weight:600;overflow-wrap:anywhere;min-width:0}
.dep-sql{font-size:11px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text-muted);margin-top:4px;white-space:normal;overflow-wrap:anywhere}
.dep-error{font-size:11px;color:var(--red);margin-top:2px}
/* PILL / BADGE */
.pill{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border:1px solid var(--border);border-radius:99px;font-size:11px;color:var(--text-muted)}
.svc-badge{display:inline-flex;align-items:center;padding:1px 7px;border-radius:4px;font-size:11px;font-weight:600;background:var(--primary-muted);color:var(--primary);border:1px solid rgba(59,130,246,.25);white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis}
/* DRAWER */
#drawerOverlay{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:39;display:none}
#drawerOverlay.open{display:block}
.drawer{position:fixed;right:0;top:0;bottom:0;width:min(1240px,98vw);background:var(--bg);border-left:1px solid var(--border);box-shadow:var(--shadow);transform:translateX(105%);transition:transform .22s ease;z-index:40;display:flex;flex-direction:column}
.drawer.open{transform:translateX(0)}
.drawer.fullscreen{left:0;width:100vw;border-left:none}
.drawer-top{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex:none}
.drawer-title-wrap{min-width:0;flex:1}
.drawer-title{font-size:16px;font-weight:700;overflow-wrap:anywhere}
.drawer-sub{font-size:12px;color:var(--text-muted);margin-top:2px;overflow-wrap:anywhere}
.drawer-actions{display:flex;gap:8px;flex:none}
.drawer-body{padding:18px;overflow-y:auto;flex:1}
/* MISC */
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.small{font-size:12px;color:var(--text-muted)}
.copy-ok{color:var(--green)}
pre{white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;background:var(--bg-subtle);border:1px solid var(--border);border-radius:8px;padding:12px;max-height:360px;overflow:auto;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.responsive-table{width:100%;overflow-x:auto;border:1px solid var(--border);border-radius:8px;background:var(--bg-subtle);margin-bottom:12px}
.responsive-table table{min-width:900px;border:0}
.responsive-table th,.responsive-table td{vertical-align:top;overflow-wrap:anywhere;word-break:break-word}
.responsive-table .col-kind{width:150px;min-width:150px}
.responsive-table .col-target{width:260px;min-width:260px}
.responsive-table .col-ms{width:72px;min-width:72px;text-align:right}
.pager{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:8px;color:var(--text-muted);font-size:12px}
.pager .btn{font-size:12px;padding:4px 8px}
.trace-toggle-panel.hidden-panel{display:none}
.explain{padding:10px 14px;border:1px solid var(--border);border-radius:8px;background:var(--bg-subtle);color:var(--text-muted);font-size:13px;margin-bottom:12px}
.tabs-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.mapCanvas{min-height:320px;background:var(--bg-subtle);border:1px solid var(--border);border-radius:10px;padding:16px;overflow:auto;margin-bottom:12px}
.nodeRow{display:flex;align-items:center;gap:10px;margin:10px 0}
.node{min-width:160px;max-width:520px;border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px;overflow-wrap:anywhere;word-break:break-word}
.node.route{border-color:var(--primary)}
.node.dep{border-color:var(--green)}
.node.errorNode{border-color:var(--red)}
.arrow-line{width:40px;height:2px;background:linear-gradient(90deg,var(--primary),transparent);position:relative;flex:none}
.arrow-line:after{content:"";position:absolute;right:0;top:-4px;border-left:7px solid var(--primary);border-top:5px solid transparent;border-bottom:5px solid transparent}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:8px 10px;border:1px solid var(--border);text-align:left}
th{background:var(--surface-raised);font-weight:600;font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--text-muted)}
.login-overlay{position:fixed;inset:0;z-index:100;display:grid;place-items:center;background:rgba(10,14,20,.96);backdrop-filter:blur(6px)}
.login-box{width:min(400px,90vw);background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:28px;box-shadow:var(--shadow)}
.login-brand{display:flex;align-items:center;gap:10px;margin-bottom:20px}
.login-form{display:flex;flex-direction:column;gap:10px}
.form-input{background:var(--bg);border:1px solid var(--border);border-radius:7px;padding:9px 12px;font:inherit;font-size:13px;color:var(--text)}
.form-input:focus{outline:none;border-color:var(--primary)}
.form-input::placeholder{color:var(--text-subtle)}
.hint{font-size:12px;color:var(--text-muted)}
.livePulse{animation:pulse 1.8s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.hidden{display:none!important}
@media(max-width:900px){.overview-grid{grid-template-columns:1fr}.kpi-row{grid-template-columns:repeat(2,1fr)}#dashboardShell{grid-template-columns:1fr}}
</style></head>
<body>
<div id="app-shell">

<!-- LOGIN OVERLAY -->
<div id="loginOverlay" class="login-overlay">
  <section class="login-box">
    <div class="login-brand">
      <div class="brand-icon" style="width:38px;height:38px;border-radius:10px"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
      <div><div style="font-size:16px;font-weight:700">Runtime Observer</div><div class="hint">Sign in to continue</div></div>
    </div>
    <form id="loginForm" class="login-form">
      <input id="loginUsername" class="form-input" autocomplete="username" placeholder="Username" required>
      <input id="loginPassword" class="form-input" type="password" autocomplete="current-password" placeholder="Password" required>
      <button class="btn btn-primary" type="submit">Sign in / bootstrap admin</button>
      <div id="loginError" class="small level-ERROR" style="color:var(--red)"></div>
    </form>
  </section>
</div>

<!-- TOPBAR -->
<div class="topbar">
  <div class="topbar-brand">
    <div class="brand-icon">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
    </div>
    <span class="brand-name">Runtime Observer</span>
  </div>
  <div class="topbar-divider"></div>
  <span id="topbarProject" class="topbar-project">No project selected</span>
  <div class="topbar-right">
    <span id="userText" class="hint"></span>
    <button id="logoutBtn" class="btn" style="font-size:12px;padding:4px 10px">Logout</button>
    <div class="topbar-divider"></div>
    <span class="status-dot livePulse" id="liveDot"></span>
    <span id="liveText" class="live-text">live refresh every 10s</span>
    <select id="refreshInterval" class="select-sm" title="Refresh interval">
      <option value="1000">1s</option>
      <option value="10000" selected>10s</option>
      <option value="20000">20s</option>
      <option value="60000">60s</option>
      <option value="0">Manual</option>
    </select>
    <button id="refreshBtn" class="icon-btn" title="Refresh now">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.07-8.97"/></svg>
    </button>
    <button id="themeToggle" class="icon-btn" title="Toggle theme">
      <svg id="themeIconSun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
      <svg id="themeIconMoon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true" style="display:none"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/></svg>
    </button>
    <span class="env-badge" id="envBadge">dev</span>
  </div>
</div>

<!-- BODY AREA -->
<div class="body-area">

<!-- PROJECT SCREEN -->
<div id="projectScreen" style="flex:1;overflow-y:auto;padding:24px">
  <div class="project-screen-header">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div>
        <div class="project-screen-title">Projects</div>
        <div class="project-screen-sub">Select a project to inspect traces and telemetry</div>
      </div>
      <button class="btn btn-primary" onclick="createProjectKey(prompt('Project name','default')||'default')">Create project SDK key</button>
    </div>
  </div>
  <div id="projectCards" class="project-grid"></div>
</div>

<!-- DASHBOARD SHELL (sidebar + main) -->
<div id="dashboardShell" class="hidden" style="flex:1;overflow:hidden;display:grid;grid-template-columns:280px minmax(0,1fr)">

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-apps" id="appTabs"></div>
    <div class="sidebar-search">
      <div class="search-wrap">
        <span class="search-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        </span>
        <input id="routeSearch" class="search-input" type="search" placeholder="Search routes...">
      </div>
    </div>
    <div class="sidebar-filter">
      <button id="showHiddenBtn" class="filter-toggle" title="Show hidden routes">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>
        Show hidden
      </button>
    </div>
    <div class="sidebar-routes" id="entrypoints"></div>
  </div>

  <!-- MAIN CONTENT -->
  <div class="main-content">
    <div class="tab-bar">
      <button class="tab-btn active" data-tab="overview">Overview</button>
      <button class="tab-btn" data-tab="requests">Requests <span class="tab-count" id="tabCountRequests">0</span></button>
      <button class="tab-btn" data-tab="logs">Logs <span class="tab-count" id="tabCountLogs">0</span></button>
      <button class="tab-btn" data-tab="errors">Errors <span class="tab-count" id="tabCountErrors">0</span></button>
      <button class="tab-btn" data-tab="dependencies">Dependencies <span class="tab-count" id="tabCountDeps">0</span></button>
    </div>
    <div class="tab-panels">

      <!-- OVERVIEW TAB -->
      <div class="tab-panel active" id="panel-overview">
        <div id="kpis" class="kpi-row"></div>
        <div id="insights" class="insight-grid"></div>
        <div class="overview-grid">
          <div class="card">
            <div class="card-header"><span class="card-title">Route Performance</span><span class="pill">p95 latency</span></div>
            <div class="card-body" id="routes"></div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Activity Summary</span><span class="pill">live</span></div>
            <div class="card-body">
              <div id="mix"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- REQUESTS TAB -->
      <div class="tab-panel" id="panel-requests">
        <div style="display:grid;grid-template-columns:minmax(360px,420px) minmax(0,1fr);gap:12px;height:100%">
          <div style="display:flex;flex-direction:column;gap:8px">
            <div class="small" style="padding:2px 0;font-weight:600;color:var(--text-muted)">Traces for selected route</div>
            <div id="traceList" class="trace-list"></div>
          </div>
          <div>
            <div class="small" style="padding:2px 0 8px;font-weight:600;color:var(--text-muted)">Logs related to selected trace</div>
            <div id="routeLogs"></div>
          </div>
        </div>
      </div>

      <!-- LOGS TAB -->
      <div class="tab-panel" id="panel-logs">
        <div class="log-toolbar">
          <div class="search-wrap" style="flex:1;min-width:200px">
            <span class="search-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            </span>
            <input id="logSearch" class="search-input" placeholder="Search log message...">
          </div>
          <select id="level" class="select-sm" title="Log level">
            <option value="">All levels</option>
            <option>ERROR</option>
            <option>WARNING</option>
            <option>INFO</option>
            <option>DEBUG</option>
          </select>
          <select id="logWindow" class="select-sm" title="Log window">
            <option value="5">Last 5m</option>
            <option value="15">Last 15m</option>
            <option value="60" selected>Last 1h</option>
            <option value="360">Last 6h</option>
            <option value="1440">Last 24h</option>
            <option value="0">All retained</option>
          </select>
          <select id="logSource" class="select-sm" title="Log source">
            <option value="all">All sources</option>
            <option value="client">Client console</option>
            <option value="backend">Backend</option>
          </select>
          <button id="searchBtn" class="btn">Search</button>
        </div>
        <div id="logs"></div>
      </div>

      <!-- ERRORS TAB -->
      <div class="tab-panel" id="panel-errors">
        <div class="overview-grid">
          <div class="card"><div class="card-header"><span class="card-title">Error clusters</span><span class="pill">grouped by fingerprint</span></div><div class="card-body" id="errorClusters"></div></div>
          <div class="card"><div class="card-header"><span class="card-title">Error timeline</span><span class="pill">24h</span></div><div class="card-body"><div id="errorTimeline"></div><div id="errors" style="margin-top:12px"></div></div></div>
        </div>
      </div>

      <!-- DEPENDENCIES TAB -->
      <div class="tab-panel" id="panel-dependencies">
        <div class="explain">Dependencies are external resources your app interacted with: database queries, outbound HTTP calls, LLM calls, and package inventory. Counts and latency are aggregated per app + target + operation. Click a dependency to inspect recent samples, errors, related logs, and traces.</div>
        <div id="deps"></div>
      </div>

    </div>
  </div>
</div><!-- /dashboardShell -->

</div><!-- /body-area -->
</div><!-- /app-shell -->

<!-- DRAWER OVERLAY -->
<div id="drawerOverlay"></div>

<!-- DRAWER -->
<div id="drawer" class="drawer">
  <div class="drawer-top">
    <div class="drawer-title-wrap">
      <div id="drawerTitle" class="drawer-title">Detail</div>
      <div id="drawerSub" class="drawer-sub"></div>
    </div>
    <div class="drawer-actions">
      <button id="drawerFullscreenBtn" class="icon-btn" aria-label="Toggle fullscreen drawer" title="Toggle fullscreen">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
      </button>
      <button id="closeBtn" class="icon-btn" aria-label="Close drawer">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
  </div>
  <div id="drawerBody" class="drawer-body"></div>
</div>

<script>
(function(){
// ── INIT THEME ──
var _savedTheme=localStorage.getItem('runtimeObserverTheme');
if(_savedTheme)document.documentElement.dataset.theme=_savedTheme;
updateThemeIcon();
function updateThemeIcon(){
  var dark=document.documentElement.dataset.theme==='dark';
  var sun=document.getElementById('themeIconSun');
  var moon=document.getElementById('themeIconMoon');
  if(sun)sun.style.display=dark?'block':'none';
  if(moon)moon.style.display=dark?'none':'block';
}
window.updateThemeIcon=updateThemeIcon;

// ── STATE ──
var overview={apps:[],totals:{},routes:[],dependencies:[],recent_logs:[],recent_errors:[],event_kinds:[],log_levels:[]};
var errorSummary={totals:{},by_type:[],by_service:[]};
var errorClusters=[];
var errorTimeline=[];
var metricsSeries=[];
var tableSort={routes:{key:'p95_ms',dir:-1},logs:{key:'timestamp',dir:-1},deps:{key:'call_count',dir:-1},errors:{key:'count',dir:-1},errorTimeline:{key:'bucket',dir:-1}};
var tablePages={routes:{page:1,size:20},deps:{page:1,size:20},errors:{page:1,size:20},errorTimeline:{page:1,size:12}};
var loadingCount=0;
var projects=[];
var entries=[];
var hiddenPrefs=[];
var selectedProject='';
var selectedApp='all';
var selectedRouteId=null;
var selectedTraceId=null;
var routeState=null;
var isRefreshing=false;
var logSource='all';
var refreshTimer=null;
var refreshMs=10000;
var logWindowMinutes=Number(localStorage.getItem('runtimeObserverLogWindowMinutes')||60);
var selectedTab='overview';
var routeSearchQuery='';
var showHidden=false;
var copyCache=new Map();

// ── HELPERS ──
function $(id){return document.getElementById(id);}
function esc(v){return String(v??'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function num(n){return Number(n||0).toLocaleString();}
function fmtTs(v){
  if(!v)return '—';
  var d=new Date(v);
  return Number.isFinite(d.getTime())?d.toLocaleString(undefined,{year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'short'}):String(v);
}
function pretty(v){try{return JSON.stringify(typeof v==='string'?JSON.parse(v):v,null,2);}catch(e){return String(v??'');}}
function sortRows(rows,name){var s=tableSort[name]||{key:'',dir:1};return rows.slice().sort(function(a,b){var av=a[s.key],bv=b[s.key];var na=Number(av),nb=Number(bv);if(Number.isFinite(na)&&Number.isFinite(nb))return (na-nb)*s.dir;return String(av||'').localeCompare(String(bv||''))*s.dir;});}
function sortHeader(name,key,label){return '<th class="sortable" data-sort-table="'+name+'" data-sort-key="'+key+'">'+label+(tableSort[name]&&tableSort[name].key===key?(tableSort[name].dir>0?' ▲':' ▼'):'')+'</th>';}
function pageState(name){return tablePages[name]||null;}
function pagedRows(sorted,name){var p=pageState(name);if(!p)return sorted;var total=Math.max(1,Math.ceil(sorted.length/p.size));p.page=Math.min(Math.max(1,p.page),total);return sorted.slice((p.page-1)*p.size,p.page*p.size);}
function pagerHtml(name,total){var p=pageState(name);if(!p||total<=p.size)return '';var pages=Math.max(1,Math.ceil(total/p.size));return '<div class="pager"><button class="btn" data-page-table="'+name+'" data-page-dir="-1" '+(p.page<=1?'disabled':'')+'>Prev</button><span>Page '+p.page+' of '+pages+' &bull; '+num(total)+' rows</span><button class="btn" data-page-table="'+name+'" data-page-dir="1" '+(p.page>=pages?'disabled':'')+'>Next</button></div>';}
function setLoading(on){loadingCount=Math.max(0,loadingCount+(on?1:-1));document.body.classList.toggle('loading',loadingCount>0);}
async function withLoading(fn){setLoading(true);try{return await fn();}finally{setLoading(false);}}
function spark(rows,key,danger){var vals=rows.map(function(r){return Number(r[key]||0);});var max=Math.max(1,Math.max.apply(null,vals));return '<div class="spark">'+(vals.length?vals.slice(-24).map(function(v){return '<span class="spark-bar '+(danger?'err':'')+'" style="height:'+Math.max(3,v/max*36)+'px"></span>';}).join(''):'<span class="small">No recent data</span>')+'</div>';}

// ── THEME TOGGLE ──
function toggleTheme(){
  var next=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=next;
  localStorage.setItem('runtimeObserverTheme',next);
  updateThemeIcon();
}

// ── AUTH ──
function showLogin(){
  if(refreshTimer)clearInterval(refreshTimer);
  $('loginOverlay').classList.remove('hidden');
}
function hideLogin(user){
  $('loginOverlay').classList.add('hidden');
  $('userText').textContent=user?'signed in as '+user.username:'';
}
async function api(path,options){
  options=options||{};
  var r=await fetch(path,Object.assign({cache:'no-store'},options,{headers:Object.assign({'Content-Type':'application/json'},options.headers||{})}));
  if(r.status===401){showLogin();throw new Error('Authentication required');}
  if(!r.ok)throw new Error(await r.text());
  return r.json();
}
async function checkAuth(){
  try{var data=await api('/api/auth/me');hideLogin(data.user);return true;}
  catch(e){return false;}
}
async function loginSubmit(ev){
  ev.preventDefault();
  $('loginError').textContent='';
  var r=await fetch('/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:$('loginUsername').value,password:$('loginPassword').value})});
  if(!r.ok){$('loginError').textContent='Sign in failed';return;}
  var data=await r.json();
  hideLogin(data.user);
  setRefreshIntervalMs($('refreshInterval').value);
  refresh();
}
async function logout(){await fetch('/api/auth/logout',{method:'POST'});showLogin();}

// ── FILTER HELPERS ──
function projectApps(){
  return overview.apps.filter(function(a){return !selectedProject||a.project_name===selectedProject;});
}
function visible(rows){
  var scoped=selectedProject?rows.filter(function(r){return r.project_name===selectedProject||projectApps().some(function(a){return a.id===(r.app_id||r.id);});}):rows;
  return selectedApp==='all'?scoped:scoped.filter(function(r){return r.app_id===selectedApp||r.id===selectedApp;});
}
function appName(a){return a&&(a.display_name||a.service_name)||'unknown app';}
function filterLogSource(rows){
  if(logSource==='client')return rows.filter(function(l){return (l.service_name||'').includes('frontend')||String(l.logger_name||'').startsWith('browser.');});
  if(logSource==='backend')return rows.filter(function(l){return (l.service_name||'').includes('backend');});
  return rows;
}
function currentLogRows(){
  var rows=filterLogSource(visible(overview.recent_logs||[]));
  var level=$('level')&&$('level').value;
  if(level)rows=rows.filter(function(l){return String(l.level||'').toUpperCase()===level;});
  return rows;
}
function applyLocalLogFilters(){
  var q=($('logSearch').value||'').toLowerCase();
  var rows=currentLogRows();
  var filtered=q?rows.filter(function(l){return (l.message||'').toLowerCase().includes(q)||(l.service_name||'').toLowerCase().includes(q);}):rows;
  renderLogs('logs',filtered);
}
function dependencyLabel(dep){
  if(dep.dependency_type==='db')return ('DB '+(dep.target||'unknown')+' '+(dep.operation||'')).trim().slice(0,120);
  if(dep.dependency_type==='http')return ('HTTP '+(dep.operation||'')+' '+(dep.target||'')).trim();
  if(dep.dependency_type==='package')return 'pkg '+dep.target;
  return ((dep.dependency_type||'dep')+' '+(dep.target||'')+' '+(dep.operation||'')).trim();
}

// ── TAB SWITCHING ──
function switchTab(tabName){
  selectedTab=tabName;
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.toggle('active',b.dataset.tab===tabName);});
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.toggle('active',p.id==='panel-'+tabName);});
}

// ── ROUTE SEARCH ──
function applyRouteSearch(){
  renderEntries();
}

// ── PROJECT ACTIONS ──
function selectProject(name){
  selectedProject=name;
  selectedApp='all';
  selectedRouteId=null;
  selectedTraceId=null;
  routeState=null;
  $('topbarProject').textContent=name||'No project selected';
  render();
}
function backToProjects(){
  selectedProject='';
  selectedApp='all';
  selectedRouteId=null;
  selectedTraceId=null;
  routeState=null;
  $('topbarProject').textContent='No project selected';
  render();
}
async function copyText(value){
  try{await navigator.clipboard.writeText(value);return true;}
  catch(e){return false;}
}
async function deleteProject(name){
  var typed=prompt('Delete project "'+name+'" and all telemetry, apps, routes, logs, traces, dependencies, and SDK keys? Type the project name to confirm.');
  if(typed!==name)return;
  await api('/api/projects/'+encodeURIComponent(name),{method:'DELETE'});
  if(selectedProject===name)backToProjects();
  await refresh();
}
async function createProjectKey(name){
  var data=await api('/api/projects/'+encodeURIComponent(name)+'/api-keys',{method:'POST'});
  $('drawerTitle').textContent='New SDK key: '+data.project_name;
  $('drawerSub').textContent='Copy this key now. It is shown only once and stored hashed in the database.';
  $('drawerBody').innerHTML='<div class="tabs-row"><button class="btn btn-primary" id="copyGeneratedKey" data-api-key="'+esc(data.api_key)+'">Copy API key</button><button class="btn" data-project-keys="'+esc(data.project_name)+'">Manage keys</button></div><div style="margin-top:12px"><div class="small" style="margin-bottom:4px">Project</div><pre>'+esc(data.project_name)+'</pre><div class="small" style="margin-bottom:4px;margin-top:8px">API key</div><pre class="mono">'+esc(data.api_key)+'</pre></div>';
  openDrawer();
  $('copyGeneratedKey').onclick=async function(){$('copyGeneratedKey').textContent=await copyText(data.api_key)?'Copied':'Copy failed';};
  document.querySelectorAll('[data-project-keys]').forEach(function(b){b.onclick=function(){withLoading(function(){return showProjectKeys(b.dataset.projectKeys);});};});
  await refresh();
}
async function showProjectKeys(name){
  var keys=await api('/api/projects/'+encodeURIComponent(name)+'/api-keys');
  $('drawerTitle').textContent='SDK keys: '+name;
  $('drawerSub').textContent='Full key values are shown only when generated. Stored keys are hashed in the DB.';
  var keysHtml=keys.length?keys.map(function(k){
    return '<div class="card" style="margin-bottom:8px"><div class="card-body"><div style="display:flex;align-items:center;justify-content:space-between;gap:8px"><div><div style="font-weight:600;font-size:13px">'+esc(k.name)+'</div><div class="small mono">prefix '+esc(k.prefix)+' &bull; created '+esc(fmtTs(k.created_at))+' &bull; last used '+esc(fmtTs(k.last_used_at))+(k.revoked_at?' &bull; revoked '+esc(fmtTs(k.revoked_at)):'')+' </div></div>'+(k.revoked_at?'':'<button class="btn btn-danger" data-revoke-key="'+esc(k.id)+'" data-project="'+esc(name)+'">Revoke</button>')+'</div></div></div>';
  }).join(''):'<div class="empty-state">No SDK keys yet.</div>';
  $('drawerBody').innerHTML='<div class="tabs-row"><button class="btn btn-primary" data-project-key="'+esc(name)+'">Generate new SDK key</button></div>'+keysHtml;
  openDrawer();
  document.querySelectorAll('[data-project-key]').forEach(function(b){b.onclick=function(){withLoading(function(){return createProjectKey(b.dataset.projectKey);});};});
  document.querySelectorAll('[data-revoke-key]').forEach(function(b){
    b.onclick=async function(){
      if(confirm('Revoke this SDK key?')){
        await withLoading(async function(){
          await api('/api/projects/'+encodeURIComponent(b.dataset.project)+'/api-keys/'+encodeURIComponent(b.dataset.revokeKey),{method:'DELETE'});
          await showProjectKeys(b.dataset.project);
          await refresh();
        });
      }
    };
  });
}

// ── RENDER PROJECTS ──
function renderProjects(){
  var cards=projects.length?projects.map(function(p){
    var name=p.project_name||'default';
    return '<div class="project-card"><div class="project-card-header"><div><div class="project-name">'+esc(name)+'</div><div class="project-meta">'+num(p.app_count)+' apps &bull; '+num(p.request_count)+' requests &bull; '+num(p.error_count)+' errors &bull; '+num(p.api_key_count)+' active SDK keys</div><div class="project-meta">Created '+esc(fmtTs(p.created_at))+' &bull; Last seen '+esc(fmtTs(p.last_seen))+'</div></div></div><div class="project-actions"><button class="btn btn-primary" data-project-select="'+esc(name)+'">Open</button><button class="btn" data-project-key="'+esc(name)+'" style="font-size:12px">Generate SDK key</button><button class="btn" data-project-keys="'+esc(name)+'" style="font-size:12px">Manage keys</button><button class="btn btn-danger" data-project-delete="'+esc(name)+'" style="font-size:12px">Delete</button></div></div>';
  }).join(''):'<div class="empty-state" style="grid-column:1/-1"><p>No projects yet. Create an SDK key for the project name your app will send, configure the SDK, then exercise your app.</p><button class="btn btn-primary" onclick="createProjectKey(prompt(\'Project name\',\'default\')||\'default\')">Create first project SDK key</button></div>';
  $('projectCards').innerHTML=cards;
  document.querySelectorAll('[data-project-select]').forEach(function(b){b.onclick=function(){selectProject(b.dataset.projectSelect);};});
  document.querySelectorAll('[data-project-key]').forEach(function(b){b.onclick=function(){withLoading(function(){return createProjectKey(b.dataset.projectKey);});};});
  document.querySelectorAll('[data-project-keys]').forEach(function(b){b.onclick=function(){withLoading(function(){return showProjectKeys(b.dataset.projectKeys);});};});
  document.querySelectorAll('[data-project-delete]').forEach(function(b){b.onclick=function(){withLoading(function(){return deleteProject(b.dataset.projectDelete);});};});
  $('projectScreen').classList.toggle('hidden',!!selectedProject);
  $('dashboardShell').classList.toggle('hidden',!selectedProject);
}

// ── RENDER APPS ──
function renderApps(){
  var apps=projectApps();
  var html='<button class="app-tab" onclick="backToProjects()" style="font-size:11px">&larr; Back</button>';
  html+='<button class="app-tab '+(selectedApp==='all'?'active':'')+'" data-app="all">All apps</button>';
  apps.forEach(function(a){html+='<button class="app-tab '+(selectedApp===a.id?'active':'')+'" data-app="'+esc(a.id)+'">'+esc(appName(a))+'</button>';});
  html+='<button class="app-tab" onclick="createProjectKey(\''+esc(selectedProject)+'\')" style="font-size:11px;margin-left:auto">+ SDK key</button>';
  $('appTabs').innerHTML=html;
  document.querySelectorAll('[data-app]').forEach(function(b){
    b.onclick=function(){
      selectedApp=b.dataset.app;
      selectedRouteId=null;
      selectedTraceId=null;
      routeState=null;
      render();
      withLoading(refresh);
    };
  });
}

// ── RENDER ENTRIES ──
function renderEntries(){
  var btn=$('showHiddenBtn');
  if(btn){btn.classList.toggle('active',showHidden);btn.innerHTML=(showHidden?'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg> Hide hidden':'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg> Show hidden');}
  var rows=visible(entries).filter(function(r){
    if(Number(r.call_count||0)===0)return false;
    if(!showHidden&&r.hidden)return false;
    if(!routeSearchQuery)return true;
    return (r.route_pattern+' '+r.method).toLowerCase().includes(routeSearchQuery.toLowerCase());
  });
  if(!rows.length){
    $('entrypoints').innerHTML='<div class="empty-state" style="margin:8px">No routes'+(routeSearchQuery?' matching "'+esc(routeSearchQuery)+'"':' yet. Exercise the app and telemetry will appear here.')+'</div>';
    return;
  }
  $('entrypoints').innerHTML=rows.map(function(r){
    var method=r.method||'GET';
    var methodClass='method-'+((['GET','POST','PUT','PATCH','DELETE'].includes(method))?method:'OTHER');
    var eyeIcon=r.hidden?'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>':'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>';
    return '<button class="route-item'+(selectedRouteId===r.id?' active':'')+(r.hidden?' hidden-route':'')+'" data-route="'+esc(r.id)+'">'
      +'<div class="route-item-body">'
      +'<div class="route-top"><span class="method-badge '+methodClass+'">'+esc(method)+'</span><span class="route-path" title="'+esc(r.route_pattern)+'">'+esc(r.route_pattern)+'</span></div>'
      +'<div class="route-meta"><span>'+esc(r.service_name||'')+'</span><span>&middot;</span><span>'+num(r.call_count)+' calls</span></div>'
      +'</div>'
      +'<div class="route-item-actions"><button class="icon-btn" title="'+(r.hidden?'Restore':'Hide')+'" data-pref-action="'+(r.hidden?'restore':'hide')+'" data-pref-kind="route" data-pref-id="'+esc(r.id)+'" data-pref-app="'+esc(r.app_id)+'">'+eyeIcon+'</button></div>'
      +'</button>';
  }).join('');
  document.querySelectorAll('[data-route]').forEach(function(b){b.onclick=function(){withLoading(function(){return selectRoute(b.dataset.route);});};});
  document.querySelectorAll('[data-pref-action]').forEach(function(b){
    b.onclick=async function(ev){
      ev.preventDefault();
      ev.stopPropagation();
      await withLoading(function(){return setHidden(b.dataset.prefKind,b.dataset.prefId,b.dataset.prefApp||null,b.dataset.prefAction==='hide');});
    };
  });
}

// ── RENDER BARS ──
function renderSortableTable(id,name,columns,rows,empty){
  if(!rows.length){$(id).innerHTML='<div class="empty-state">'+esc(empty||'No data yet')+'</div>';return;}
  var sorted=sortRows(rows,name);
  var pageRows=pagedRows(sorted,name);
  var start=pageState(name)?(pageState(name).page-1)*pageState(name).size:0;
  $(id).innerHTML='<div class="table-wrap"><table><thead><tr>'+columns.map(function(c){return sortHeader(name,c.key,c.label);}).join('')+'</tr></thead><tbody>'+pageRows.map(function(r,i){return '<tr data-row-index="'+(start+i)+'">'+columns.map(function(c){return '<td>'+esc(c.render?c.render(r):r[c.key])+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table></div>'+pagerHtml(name,sorted.length);
}
function wireSortTables(){
  document.querySelectorAll('[data-sort-table]').forEach(function(th){th.onclick=function(){var name=th.dataset.sortTable,key=th.dataset.sortKey;var cur=tableSort[name]||{};tableSort[name]={key:key,dir:cur.key===key?-cur.dir:1};if(pageState(name))pageState(name).page=1;render();};});
  document.querySelectorAll('[data-page-table]').forEach(function(btn){btn.onclick=function(){var p=pageState(btn.dataset.pageTable);if(!p)return;p.page+=Number(btn.dataset.pageDir||0);render();};});
}
function renderBars(id,rows,label,value,danger){
  var max=Math.max(1,Math.max.apply(null,rows.map(function(r){return Number(r[value]||0);})));
  $(id).innerHTML=rows.length?rows.slice(0,12).map(function(r){
    var pct=Math.max(4,Number(r[value]||0)/max*100);
    return '<div class="bar-row"><span class="bar-label" title="'+esc(r[label])+'">'+esc(String(r[label]||'').slice(0,30))+'</span><div class="bar-track"><div class="bar-fill'+(danger?' err':'')+'" style="width:'+pct+'%"></div></div><span class="bar-val">'+num(r[value])+'</span></div>';
  }).join(''):'<div class="empty-state">No data yet</div>';
}

// ── RENDER MIX ──
var eventLabels={log_record:'Logs',db_query:'Database queries',http_client_call:'HTTP/API calls',route_discovered:'Entry points discovered',request_finished:'Requests completed',request_started:'Requests started',sdk_diagnostic:'SDK diagnostics',app_started:'App starts',span_started:'Spans/functions',span_finished:'Spans/functions',dependency_inventory:'Dependency inventory',exception_raised:'Exceptions'};
function sumMix(rows,key){
  var scoped=visible(rows||[]);
  var grouped=new Map();
  scoped.forEach(function(r){
    var raw=r[key]||'unknown';
    var lbl=eventLabels[raw]||String(raw).replace(/_/g,' ');
    grouped.set(lbl,(grouped.get(lbl)||0)+Number(r.count||0));
  });
  return Array.from(grouped.entries()).map(function(e){return {label:e[0],value:e[1]};}).sort(function(a,b){return b.value-a.value;});
}
function renderMix(){
  var kinds=sumMix(overview.event_kinds,'kind').filter(function(r){return r.label!=='SDK diagnostics'||r.value>0;});
  var levels=sumMix(overview.log_levels,'level');
  $('mix').innerHTML='<div class="small" style="margin-bottom:8px;font-weight:600">Activity by kind</div><div id="kindBars"></div><div class="small" style="margin:12px 0 8px;font-weight:600">Logs by level</div><div id="levelBars"></div>';
  renderBars('kindBars',kinds,'label','value',false);
  renderBars('levelBars',levels,'label','value',true);
}

// ── RENDER INSIGHTS ──
function renderInsights(routes,logs,errors,deps){
  var reqSeries=metricsSeries.reduce(function(a,r){return a+Number(r.requests||0);},0);
  var errSeries=metricsSeries.reduce(function(a,r){return a+Number(r.request_errors||0)+Number(r.error_logs||0)+Number(r.exceptions||0);},0);
  var slow=routes.slice().sort(function(a,b){return Number(b.p95_ms||0)-Number(a.p95_ms||0);})[0];
  var noisy=logs.reduce(function(m,l){var k=l.service_name||'unknown';m[k]=(m[k]||0)+1;return m;},{});
  var noisyName=Object.keys(noisy).sort(function(a,b){return noisy[b]-noisy[a];})[0]||'—';
  $('insights').innerHTML='<div class="insight-card"><div class="insight-title">Traffic trend</div><div class="insight-value">'+num(reqSeries)+'</div>'+spark(metricsSeries,'requests',false)+'</div>'+
    '<div class="insight-card"><div class="insight-title">Error signals</div><div class="insight-value" style="color:var(--red)">'+num(errSeries)+'</div>'+spark(metricsSeries,'error_logs',true)+'</div>'+
    '<div class="insight-card"><div class="insight-title">Slowest route</div><div class="insight-value">'+esc(slow?Math.round(Number(slow.p95_ms||0))+'ms':'—')+'</div><div class="small mono">'+esc(slow?(slow.method+' '+slow.route_pattern):'No route latency')+'</div></div>'+
    '<div class="insight-card"><div class="insight-title">Noisiest service</div><div class="insight-value">'+esc(noisyName)+'</div><div class="small">'+num(noisy[noisyName]||0)+' logs in selected window</div></div>';
}

// ── RENDER DEPENDENCIES ──
function renderDependencies(rows){
  renderSortableTable('deps','deps',[{key:'display',label:'Dependency'},{key:'service_name',label:'Service'},{key:'call_count',label:'Calls'},{key:'error_count',label:'Errors'},{key:'p95_duration_ms',label:'p95 ms',render:function(r){return r.p95_duration_ms?Math.round(Number(r.p95_duration_ms)):'';}}],rows,'No dependency calls yet');
  document.querySelectorAll('#deps tbody tr').forEach(function(tr){tr.style.cursor='pointer';tr.onclick=function(){var dep=sortRows(rows,'deps')[Number(tr.dataset.rowIndex||0)];withLoading(function(){return openDependency(dep);});};});
  return;
  var max=Math.max(1,Math.max.apply(null,rows.map(function(r){return Number(r.call_count||0);})));
  $('deps').innerHTML=rows.length?rows.slice(0,12).map(function(r){
    var sample=r.last_sample||{};
    var p=sample.payload||{};
    var who=p.source_function||p.route_pattern||p.source_file||r.service_name||'unknown caller';
    var sql=p.rendered_statement||p.statement_template||p.statement_fingerprint||'';
    var pct=Math.max(4,Number(r.call_count||0)/max*100);
    var payload=JSON.stringify(r);
    return '<div class="dep-card" data-dep="'+esc(payload)+'"><div class="dep-header"><span class="dep-name">'+esc(r.display)+'</span><span class="pill">'+num(r.call_count)+' calls</span></div><div class="bar-row"><span class="bar-label small">'+esc(who)+'</span><div class="bar-track" style="flex:1"><div class="bar-fill" style="width:'+pct+'%"></div></div><span class="bar-val">'+(r.p95_duration_ms?Math.round(Number(r.p95_duration_ms))+'ms':'')+'</span></div><div class="dep-sql">'+esc((sql||(r.service_name||'')+' '+(r.operation||'')).slice(0,180))+'</div>'+(r.error_count?'<div class="dep-error">'+num(r.error_count)+' errors</div>':'')+'</div>';
  }).join(''):'<div class="empty-state">No dependency calls yet</div>';
  document.querySelectorAll('.dep-card').forEach(function(el){el.onclick=function(){openDependency(JSON.parse(el.dataset.dep));};});
}

// ── RENDER ERRORS ──
function renderErrors(){
  var rows=visible(overview.recent_errors||[]);
  var clusters=visible(errorClusters||[]);
  renderSortableTable('errorClusters','errors',[{key:'type',label:'Type'},{key:'normalized_message',label:'Message',render:function(r){return String(r.normalized_message||'').slice(0,90);}},{key:'service_name',label:'Service'},{key:'route_pattern',label:'Route',render:function(r){return ((r.method||'')+' '+(r.route_pattern||'')).trim();}},{key:'count',label:'Count'},{key:'last_seen',label:'Last seen',render:function(r){return fmtTs(r.last_seen);}}],clusters,'No captured errors.');
  document.querySelectorAll('#errorClusters tbody tr').forEach(function(tr){tr.style.cursor='pointer';tr.onclick=function(){var e=sortRows(clusters,'errors')[Number(tr.dataset.rowIndex||0)];withLoading(function(){return openError(e.app_id,e.id);});};});
  $('errorTimeline').innerHTML=spark(errorTimeline,'count',true)+'<div class="small" style="margin:6px 0 10px">'+num(errorTimeline.reduce(function(a,r){return a+Number(r.count||0);},0))+' exceptions in timeline window</div><div id="errorTimelineTable"></div>';
  renderSortableTable('errorTimelineTable','errorTimeline',[{key:'bucket',label:'Time',render:function(r){return fmtTs(r.bucket);}},{key:'type',label:'Type'},{key:'project_name',label:'Project'},{key:'service_name',label:'Service'},{key:'count',label:'Count'}],errorTimeline,'No error timeline events.');
  $('errors').innerHTML=rows.length?rows.map(function(e){
    return '<button class="error-item" data-error="'+esc(e.app_id)+'|'+esc(e.id)+'"><div class="error-header"><span class="error-type">'+esc(e.type)+'</span><span class="pill" style="color:var(--red)">'+num(e.count)+'x</span></div><div class="error-msg">'+esc(e.normalized_message)+'</div><div class="error-meta">'+esc(e.service_name)+' &bull; '+esc(fmtTs(e.last_seen))+' &bull; trace '+esc(e.sample_trace_id||'none')+'</div></button>';
  }).join(''):'<div class="empty-state">No captured errors.</div>';
  document.querySelectorAll('[data-error]').forEach(function(b){
    b.onclick=function(){var parts=b.dataset.error.split('|');withLoading(function(){return openError(parts[0],parts[1]);});};
  });
}

// ── COPY STATE ──
function logCopyState(logId){return (copyCache.get('log:'+logId)||{}).status||'missing';}
function logCopyLabel(logId){var s=logCopyState(logId);if(s==='loading')return 'Preparing...';if(s==='error')return 'Retry prepare';return 'Copy for AI';}

// ── RENDER LOGS ──
function renderLogs(target,rows){
  if(target==='logs'){
    renderSortableTable(target,'logs',[{key:'timestamp',label:'Time',render:function(r){return fmtTs(r.timestamp);}},{key:'level',label:'Level'},{key:'service_name',label:'Service'},{key:'message',label:'Message',render:function(r){return String(r.message||'').slice(0,120);}},{key:'logger_name',label:'Logger'}],rows,'No logs found');
    document.querySelectorAll('#logs tbody tr').forEach(function(tr){tr.style.cursor='pointer';tr.onclick=function(){withLoading(function(){return openLog(sortRows(rows,'logs')[Number(tr.dataset.rowIndex||0)]);});};});
    return;
  }
  $(target).innerHTML=rows.length?rows.map(function(l){
    var state=logCopyState(l.id);
    var level=l.level||'LOG';
    return '<div class="log-item" data-log=\''+esc(JSON.stringify(l))+'\'><div class="log-header"><span class="level-badge level-'+esc(level)+'">'+esc(level)+'</span>'+(l.service_name?'<span class="svc-badge" title="'+esc(l.service_name)+'">'+esc(l.service_name)+'</span>':'')+'<span class="small" style="margin-left:auto">'+esc(fmtTs(l.timestamp))+'</span></div><div class="log-body">'+esc(l.message)+'</div><div class="log-footer"><span class="small mono">'+esc(l.logger_name||'')+(l.trace_id?' &bull; trace '+esc(l.trace_id):'')+'</span><button class="btn" style="font-size:11px;padding:3px 8px" data-copy-log="'+esc(l.id)+'" '+(state==='loading'?'disabled':'')+'>'+logCopyLabel(l.id)+'</button></div></div>';
  }).join(''):'<div class="empty-state">No logs found</div>';
  document.querySelectorAll('#'+target+' .log-item').forEach(function(el){el.onclick=function(){withLoading(function(){return openLog(JSON.parse(el.dataset.log));});};});
  document.querySelectorAll('#'+target+' [data-copy-log]').forEach(function(btn){
    btn.onclick=async function(ev){ev.preventDefault();ev.stopPropagation();await copyLog(btn.dataset.copyLog,btn);};
  });
}

// ── SELECTED TRACE LOGS ──
function selectedTraceLogs(){
  if(!routeState)return [];
  if(!selectedTraceId)return routeState.logs||[];
  var logs=routeState.logs||[];
  var exact=logs.filter(function(l){return l.trace_id===selectedTraceId;});
  if(exact.length)return exact;
  var trace=(routeState.traces||[]).find(function(t){return t.id===selectedTraceId;});
  if(!trace||!trace.finished_at)return [];
  var base=new Date(trace.finished_at).getTime();
  return logs.filter(function(l){
    var ts=new Date(l.timestamp||0).getTime();
    return l.route_id===trace.route_id&&Number.isFinite(ts)&&Math.abs(ts-base)<=15000;
  });
}

// ── RENDER TRACE LIST ──
function renderTraceList(){
  if(!routeState){
    $('traceList').innerHTML='<div class="empty-state">Pick an entry point from the sidebar.</div>';
    $('routeLogs').innerHTML='<div class="empty-state">Route/request logs appear here.</div>';
    return;
  }
  var traces=routeState.traces||[];
  $('traceList').innerHTML=traces.length?traces.map(function(t){
    var ok=Number(t.status_code||200)<400;
    return '<button class="trace-item'+(selectedTraceId===t.id?' active':'')+'" data-trace="'+esc(t.id)+'"><div class="trace-header"><span class="trace-status '+(ok?'ok':'err')+'"></span><div class="trace-info"><span class="trace-code '+(ok?'':'level-ERROR')+'">'+esc(t.status_code||'')+'</span> <span class="trace-route">'+esc(t.route_pattern)+'</span></div><span class="trace-ms">'+Math.round(Number(t.duration_ms||0))+'ms</span></div><div class="trace-meta">'+esc(t.service_name)+' &bull; '+esc(fmtTs(t.finished_at||t.started_at))+' &bull; '+num(t.log_count)+' logs</div></button>';
  }).join(''):'<div class="empty-state">No request traces for this route yet.</div>';
  document.querySelectorAll('[data-trace]').forEach(function(b){b.onclick=function(){withLoading(function(){return openTraceMap(b.dataset.trace);});};});
  renderLogs('routeLogs',selectedTraceLogs());
}

// ── ROUTE SELECTION ──
async function selectRoute(routeId){
  selectedRouteId=routeId;
  selectedTraceId=null;
  switchTab('requests');
  await loadRoute(routeId,true);
  render();
}
async function loadRoute(routeId,openFirst){
  routeState=await api('/api/routes/'+encodeURIComponent(routeId)+'/requests');
  var r=routeState.route;
  if(openFirst&&routeState.traces&&routeState.traces.length)selectedTraceId=routeState.traces[0].id;
}

// ── LOG WINDOW ──
function logWindowQuery(){return 'log_window_minutes='+encodeURIComponent(logWindowMinutes)+'&log_limit=1000';}
function logWindowStartParam(){if(!logWindowMinutes)return '';return new Date(Date.now()-logWindowMinutes*60*1000).toISOString();}
function syncLogWindowSelect(){var s=$('logWindow');if(s)s.value=String(logWindowMinutes);}

// ── RENDER KPI ──
function kpi(label,value){return '<div class="kpi-card"><div class="kpi-num">'+num(value)+'</div><div class="kpi-label">'+label+'</div></div>';}

// ── MAIN RENDER ──
function render(){
  renderProjects();
  if(!selectedProject)return;
  renderApps();
  renderEntries();
  var routes=visible(overview.routes||[]);
  var allLogs=currentLogRows();
  var errors=visible(overview.recent_errors||[]);
  var deps=visible(overview.dependencies||[]).map(function(d){return Object.assign({},d,{display:dependencyLabel(d)});});
  var totalReq=selectedApp==='all'?overview.totals.request_count:routes.reduce(function(a,r){return a+Number(r.call_count||0);},0);
  // KPIs
  $('kpis').innerHTML=kpi('Applications',selectedApp==='all'?overview.apps.length:1)+kpi('Requests',totalReq)+kpi('Errors',selectedApp==='all'?overview.totals.exception_count:errors.length)+kpi('Logs',selectedApp==='all'?overview.totals.log_count:allLogs.length)+kpi('Events',overview.totals.event_count);
  // Tab counts
  var traces=routeState?routeState.traces||[]:[];
  $('tabCountRequests').textContent=traces.length;
  $('tabCountLogs').textContent=allLogs.length;
  $('tabCountErrors').textContent=errors.length;
  $('tabCountDeps').textContent=deps.length;
  // Tab content
  renderInsights(routes,allLogs,errors,deps);
  renderSortableTable('routes','routes',[{key:'method',label:'Method'},{key:'route_pattern',label:'Route'},{key:'service_name',label:'Service'},{key:'call_count',label:'Calls'},{key:'error_count',label:'Errors'},{key:'p95_ms',label:'p95 ms',render:function(r){return Math.round(Number(r.p95_ms||0));}},{key:'last_seen',label:'Last seen',render:function(r){return fmtTs(r.last_seen);}}],routes,'No routes yet');
  renderMix();
  renderErrors();
  renderDependencies(deps);
  renderLogs('logs',allLogs);
  renderTraceList();
  wireSortTables();
  // Sync log source select
  var ls=$('logSource');if(ls)ls.value=logSource;
}

// ── REFRESH ──
function refreshLabel(){return refreshMs===0?'manual refresh':'live refresh every '+refreshMs/1000+'s';}
function setRefreshIntervalMs(ms){
  refreshMs=Number(ms);
  if(refreshTimer)clearInterval(refreshTimer);
  refreshTimer=null;
  $('liveDot').classList.toggle('livePulse',refreshMs!==0);
  $('liveText').textContent=refreshLabel();
  if(refreshMs>0)refreshTimer=setInterval(refresh,refreshMs);
}
async function setHidden(kind,id,appId,hidden){
  if(hidden){
    await api('/api/preferences/hidden',{method:'POST',body:JSON.stringify({target_kind:kind,target_id:id,app_id:appId})});
    if(kind==='route'&&selectedRouteId===id){selectedRouteId=null;selectedTraceId=null;routeState=null;}
  }else{
    await api('/api/preferences/hidden/'+encodeURIComponent(kind)+'/'+encodeURIComponent(id)+(appId?'?app_id='+encodeURIComponent(appId):''),{method:'DELETE'});
  }
  await refresh();
}
async function refresh(){
  if(isRefreshing)return;
  isRefreshing=true;
  try{
    var scope=selectedProject?'&project_name='+encodeURIComponent(selectedProject):'';
    var appScope=selectedApp&&selectedApp!=='all'?'&app_id='+encodeURIComponent(selectedApp):'';
    var results=await Promise.all([
      api('/api/overview?'+logWindowQuery()),
      api('/api/projects'),
      api('/api/entrypoints?include_hidden=true'),
      api('/api/preferences/hidden'),
      api('/api/errors/summary?log_window_minutes='+encodeURIComponent(logWindowMinutes)+scope+appScope),
      api('/api/errors/clusters?limit=100'+scope+appScope),
      api('/api/errors/timeline?window_minutes=1440&bucket_minutes=60'+scope+appScope),
      api('/api/metrics/timeseries?window_minutes=1440&bucket_minutes=60'+scope+appScope)
    ]);
    overview=results[0];projects=results[1];entries=results[2];hiddenPrefs=results[3];errorSummary=results[4];errorClusters=results[5];errorTimeline=results[6];metricsSeries=results[7];
    if(selectedProject&&!projects.some(function(p){return p.project_name===selectedProject;})){selectedProject='';}
    $('liveText').textContent=refreshLabel()+' &bull; logs '+(logWindowMinutes?'last '+logWindowMinutes+'m':'all retained')+' &bull; updated '+new Date().toLocaleTimeString();
    if(selectedRouteId)await loadRoute(selectedRouteId,false);
    render();
    syncLogWindowSelect();
  }catch(err){
    $('liveText').textContent='telemetry refresh failed';
    console.error(err);
  }finally{
    isRefreshing=false;
  }
}

// ── SEARCH LOGS ──
async function searchLogs(){
  var q=encodeURIComponent($('logSearch').value);
  var level=encodeURIComponent($('level').value);
  var start=encodeURIComponent(logWindowStartParam());
  var rows=await api('/api/logs?text='+q+'&level='+level+'&start='+start+'&limit=1000');
  renderLogs('logs',filterLogSource(visible(rows)));
}

// ── DRAWER ──
function openDrawer(){
  $('drawer').classList.add('open');
  $('drawerOverlay').classList.add('open');
}
function closeDrawer(){
  $('drawer').classList.remove('open');
  $('drawerOverlay').classList.remove('open');
}
function toggleDrawerFullscreen(){
  $('drawer').classList.toggle('fullscreen');
}

// ── COPY HELPERS ──
function showCopyStatus(message,isError){
  var el=$('copyStatus');
  if(!el){el=document.createElement('span');el.id='copyStatus';el.className='small';$('drawerBody')&&$('drawerBody').prepend(el);}
  el.textContent=message;
  el.style.display='inline-flex';
  el.style.marginLeft='8px';
  el.style.color=isError?'var(--red)':'var(--green)';
  if(!isError&&message.startsWith('✓'))setTimeout(function(){el.textContent='';},3500);
}
function setCopyButton(btn,text,disabled){
  if(!btn)return;
  btn.textContent=text;
  btn.disabled=!!disabled;
  btn.style.opacity=disabled?'.7':'1';
}
function preparedTextarea(){
  var area=$('preparedCopyText');
  if(!area){
    area=document.createElement('textarea');
    area.id='preparedCopyText';
    area.setAttribute('aria-hidden','true');
    area.style.cssText='position:fixed;left:0;top:0;width:1px;height:1px;opacity:.01;z-index:-1';
    document.body.appendChild(area);
  }
  return area;
}
function writeClipboardTextNow(text){
  var area=preparedTextarea();
  area.value=text;
  area.focus();
  area.select();
  area.setSelectionRange(0,area.value.length);
  var ok=document.execCommand('copy');
  if(!ok)throw new Error('copy command failed');
}
function showManualCopy(text){
  $('drawerTitle').textContent='Manual copy';
  $('drawerSub').textContent='Automatic clipboard copy was blocked by the browser';
  $('drawerBody').innerHTML='<div class="explain" style="color:var(--red)">Browser blocked automatic copy. The full AI context is selected below. Press Cmd/Ctrl+C.</div><textarea id="manualCopyText" style="width:100%;min-height:70vh;background:var(--bg-subtle);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px"></textarea>';
  openDrawer();
  var area=$('manualCopyText');
  area.value=text;
  area.focus();
  area.select();
  area.setSelectionRange(0,area.value.length);
}
function updateLogCopyButtons(logId){
  document.querySelectorAll('[data-copy-log="'+CSS.escape(logId)+'"]').forEach(function(btn){
    var state=logCopyState(logId);
    btn.disabled=state==='loading';
    btn.textContent=logCopyLabel(logId);
  });
}
function prepareLogCopyBackground(logId){
  var key='log:'+logId;
  if(copyCache.has(key))return;
  copyCache.set(key,{status:'loading',text:''});
  api('/api/logs/'+encodeURIComponent(logId)+'/agent-context').then(function(data){
    copyCache.set(key,{status:'ready',text:data.text});
    updateLogCopyButtons(logId);
  }).catch(function(err){
    console.error(err);
    copyCache.set(key,{status:'error',text:''});
    updateLogCopyButtons(logId);
  });
}
function prepareCopy(key,path,readyText){
  readyText=readyText||'Ready to copy';
  copyCache.set(key,{status:'loading',text:''});
  return api(path).then(function(data){
    copyCache.set(key,{status:'ready',text:data.text});
    preparedTextarea().value=data.text;
    showCopyStatus(readyText,false);
    return data.text;
  }).catch(function(err){
    console.error(err);
    copyCache.set(key,{status:'error',text:''});
    showCopyStatus('Failed to prepare copy context',true);
    throw err;
  });
}
function copyPrepared(key,successMessage,btn,resetText){
  var item=copyCache.get(key);
  if(!item){showCopyStatus('Preparing copy context. Click again when ready.',true);setCopyButton(btn,'Preparing...',true);setTimeout(function(){setCopyButton(btn,resetText,false);},900);return;}
  if(item.status==='loading'){showCopyStatus('Still preparing copy context — try again in a second',true);setCopyButton(btn,'Preparing...',true);setTimeout(function(){setCopyButton(btn,resetText,false);},900);return;}
  if(item.status==='error'){showCopyStatus('Copy context failed to prepare',true);setCopyButton(btn,'Copy failed',false);return;}
  try{
    writeClipboardTextNow(item.text);
    showCopyStatus(successMessage,false);
    setCopyButton(btn,'✓ Copied',false);
    setTimeout(function(){setCopyButton(btn,resetText,false);},2500);
  }catch(err){
    showManualCopy(item.text);
    setCopyButton(btn,'Manual copy opened',false);
  }
}
async function copyLog(logId,btn){
  var key='log:'+logId;
  var existing=copyCache.get(key);
  if(!existing){prepareLogCopyBackground(logId);setCopyButton(btn,'Preparing...',true);showCopyStatus('Preparing log context. The button will enable automatically.',true);return;}
  if(existing.status==='loading'){setCopyButton(btn,'Preparing...',true);showCopyStatus('Still preparing log context. The button will enable automatically.',true);return;}
  if(existing.status==='error'){copyCache.delete(key);prepareLogCopyBackground(logId);setCopyButton(btn,'Preparing...',true);showCopyStatus('Retrying log context preparation...',true);return;}
  copyPrepared(key,'✓ Copied log context for AI agent',btn,'Copy for AI');
}
function copyTrace(traceId,btn){
  var key='trace:'+traceId;
  if(!copyCache.has(key)){prepareCopy(key,'/api/traces/'+encodeURIComponent(traceId)+'/agent-context','Ready to copy trace context');setCopyButton(btn,'Preparing...',true);showCopyStatus('Preparing trace context. Click again when ready.',true);return;}
  copyPrepared(key,'✓ Copied full trace context for AI agent',btn,'Copy full trace for AI');
}
function copyDependency(depId,btn){
  var key='dep:'+depId;
  if(!copyCache.has(key)){prepareCopy(key,'/api/dependencies/'+encodeURIComponent(depId)+'/agent-context','Ready to copy dependency context');setCopyButton(btn,'Preparing...',true);showCopyStatus('Preparing dependency context. Click again when ready.',true);return;}
  copyPrepared(key,'✓ Copied dependency errors/context for AI agent',btn,'Copy dependency errors for AI');
}

// ── OPEN DEPENDENCY ──
async function openDependency(dep){
  var data=await api('/api/dependencies/'+encodeURIComponent(dep.id)+'/context');
  var sample=dep.last_sample||{};
  var errorRows=(data.error_samples||[]).map(function(e){
    return '<div class="log-item"><div class="log-header"><span class="level-badge level-ERROR">ERROR</span><span class="small">'+esc(e.timestamp)+(e.trace_id?' &bull; trace '+esc(e.trace_id):' &bull; no trace')+'</span></div><div class="log-body mono">'+esc(e.payload&&(e.payload.error_type||e.payload.error)||'dependency error')+'</div><div>'+esc((e.payload&&e.payload.error_message)||'')+'</div><pre>'+esc(JSON.stringify(e.payload,null,2))+'</pre>'+(e.trace_id?'<button class="btn" style="margin-top:8px" onclick="openTraceMap(\''+esc(e.trace_id)+'\')">Open trace</button>':'')+'</div>';
  }).join('');
  var related=(data.related_logs||[]).map(function(l){
    return '<div class="log-item"><div class="log-header"><span class="level-badge level-'+esc(l.level)+'">'+esc(l.level||'LOG')+'</span><span class="small">'+esc(l.service_name)+' &bull; '+esc(fmtTs(l.timestamp))+'</span></div><div class="log-body">'+esc(l.message)+'</div><div class="small mono">'+esc(l.logger_name||'')+'</div></div>';
  }).join('');
  $('drawerTitle').textContent='Dependency context';
  $('drawerSub').textContent=(dep.service_name||'')+' &bull; '+(dep.call_count||0)+' calls &bull; '+(dep.error_count||0)+' errors';
  $('drawerBody').innerHTML='<div class="explain">This is an aggregate dependency. The error samples below are the actual failed events that produced the error count.</div><div class="tabs-row"><button class="btn btn-primary" data-copy-dep="'+esc(dep.id)+'">Copy dependency errors for AI</button><span id="copyStatus" class="small copy-ok" style="min-width:200px">Copy context is prepared only when requested.</span>'+(sample.trace_id?'<button class="btn" data-open-trace="'+esc(sample.trace_id)+'">Open latest sample trace</button>':'')+'</div><h3 style="margin:14px 0 8px">Error samples</h3><div>'+(errorRows||'<div class="empty-state">No individual error payloads retained for this dependency yet.</div>')+'</div><h3 style="margin:14px 0 8px">Related logs</h3><div>'+(related||'<div class="empty-state">No nearby logs found.</div>')+'</div><h3 style="margin:14px 0 8px">Aggregate + latest sample</h3><pre>'+esc(pretty(data))+'</pre>';
  openDrawer();
}

// ── OPEN LOG ──
async function openLog(log){
  if(log.trace_id){await openTraceMap(log.trace_id);return;}
  $('drawerTitle').textContent='Log record';
  $('drawerSub').textContent=(log.service_name||'')+' &bull; '+fmtTs(log.timestamp);
  $('drawerBody').innerHTML='<div class="tabs-row"><button class="btn btn-primary" data-copy-log="'+esc(log.id)+'">Copy log context for AI</button><span id="copyStatus" class="small copy-ok">Copy context is prepared only when requested.</span></div><div class="explain">This log has no trace id, so only the record and nearby logs are available.</div><pre>'+esc(pretty(log))+'</pre>';
  openDrawer();
}

// ── TRACE MAP ──
function eventPayload(item){try{return JSON.parse(item.payload_json||'{}');}catch(e){return {};}}
function renderMap(data){
  var traces=data.traces||[],deps=data.dependencies||[],exceptions=data.exceptions||[],logs=data.logs||[],spans=data.spans||[];
  var nodes=[];
  traces.forEach(function(t){nodes.push('<div class="nodeRow"><div class="node route"><div style="font-size:11px;font-weight:700;color:var(--primary);margin-bottom:4px">HTTP ROUTE</div><div style="font-size:12px">'+esc(t.service_name)+'</div><div class="mono" style="font-size:12px">'+esc(t.method)+' '+esc(t.route_pattern)+'</div><div class="small">'+Math.round(Number(t.duration_ms||0))+'ms &bull; status '+esc(t.status_code||'')+'</div></div></div>');});
  spans.filter(function(s){return s.kind==='function';}).slice(0,12).forEach(function(s){nodes.push('<div class="nodeRow"><div class="arrow-line"></div><div class="node"><div style="font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:4px">FUNCTION</div><div class="mono" style="font-size:12px">'+esc(s.name||'handler')+'</div><div class="small">'+Math.round(Number(s.duration_ms||0))+'ms &bull; '+esc(s.status||'')+'</div></div></div>');});
  logs.slice(0,12).forEach(function(l){nodes.push('<div class="nodeRow"><div class="arrow-line"></div><div class="node"><div style="font-size:11px;font-weight:700;color:var(--text-muted);margin-bottom:4px">'+esc(l.source_function||l.logger_name||'LOG')+'</div><div style="font-size:12px">'+esc(l.message).slice(0,140)+'</div><div class="small">'+esc(l.service_name)+' &bull; '+esc(l.level||'LOG')+'</div></div></div>');});
  deps.slice(0,20).forEach(function(d){
    var p=eventPayload(d);
    var tables=Array.isArray(p.tables)?p.tables.join(', '):'';
    var target=p.target||p.host||p.database||p.model||tables||'dependency';
    var operation=p.rendered_statement||p.statement_template||p.statement_fingerprint||p.operation||p.method||p.provider||'';
    var title=d.kind==='db_query'?'DB QUERY':d.kind==='http_client_call'?'HTTP CLIENT':'DEPENDENCY';
    nodes.push('<div class="nodeRow"><div class="arrow-line"></div><div class="node dep"><div style="font-size:11px;font-weight:700;color:var(--green);margin-bottom:4px">'+title+'</div><div style="font-size:12px">'+esc(target)+'</div><div class="small mono">'+esc(operation).slice(0,360)+'</div><div class="small">'+(p.duration_ms?Math.round(Number(p.duration_ms))+'ms':'')+''+(p.row_count!=null?' &bull; rows '+esc(p.row_count):'')+(p.status_code?' &bull; status '+esc(p.status_code):'')+'</div></div></div>');
  });
  exceptions.forEach(function(e){nodes.push('<div class="nodeRow"><div class="arrow-line"></div><div class="node errorNode"><div style="font-size:11px;font-weight:700;color:var(--red);margin-bottom:4px">EXCEPTION</div><div style="font-size:12px;font-weight:600">'+esc(e.type)+'</div><div class="small">'+esc(e.normalized_message)+'</div></div></div>');});
  return '<div class="mapCanvas">'+(nodes.length?nodes.join(''):'<div class="empty-state">No map nodes for this trace yet.</div>')+'</div>';
}
function dependencyTarget(p){return p.target||p.host||p.database||p.model||(Array.isArray(p.tables)?p.tables.join(', '):'');}
function dependencyOperation(p){return p.rendered_statement||p.statement_template||p.statement_fingerprint||p.operation||p.method||p.request_body_preview||p.provider||'';}
function renderDependencyDetails(deps){
  var rows=(deps||[]).map(function(d){
    var p=eventPayload(d), params=p.parameters||p.params||'';
    return '<tr><td class="col-kind">'+esc(d.kind||'dependency')+'</td><td class="col-target">'+esc(dependencyTarget(p)||'dependency')+'</td><td class="mono">'+esc(dependencyOperation(p))+(params?'<div class="small mono" style="margin-top:6px">params: '+esc(String(params).slice(0,500))+'</div>':'')+'</td><td class="col-ms">'+(p.duration_ms?Math.round(Number(p.duration_ms)):'')+'</td></tr>';
  }).join('');
  if(!rows)return '<div class="empty-state">No dependency calls captured for this request.</div>';
  return '<div class="responsive-table"><table><thead><tr><th class="col-kind">kind</th><th class="col-target">target</th><th>operation / input</th><th class="col-ms">ms</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
function renderRawTimeline(items){
  items=(items||[]).slice(0,160);
  return items.map(function(item){var ts=item.timestamp||item.started_at||item.finished_at||'';var kind=item.kind||item.type||'event';return '<details style="margin-bottom:4px"><summary style="cursor:pointer;padding:6px 10px;border-radius:6px 6px 0 0;border:1px solid var(--border);background:var(--surface);font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;list-style:none;display:flex;gap:10px;align-items:center"><span style="color:var(--text-subtle);flex:none">'+esc(ts?new Date(ts).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3}):'—')+'</span><span style="color:var(--primary);flex:none">'+esc(kind)+'</span><span style="color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">'+esc(item.message||item.name||item.route_pattern||item.target||item.operation||'')+'</span></summary><pre style="margin:0 0 0;border-radius:0 0 6px 6px;border:1px solid var(--border);border-top:none">'+esc(JSON.stringify(item,null,2))+'</pre></details>';}).join('')||'<div class="empty-state">No timeline events</div>';
}
function renderTraceViewToggle(hasGrouped){
  if(!hasGrouped)return '';
  return '<div class="tabs-row"><button class="btn btn-primary" data-trace-view="grouped">Grouped map</button><button class="btn" data-trace-view="raw">Raw timeline</button></div>';
}

async function openTraceMap(traceId){
  selectedTraceId=traceId;
  renderTraceList();
  copyCache.delete('trace:'+traceId);
  $('drawerTitle').textContent='Triggered map';
  $('drawerSub').textContent='trace '+traceId;
  $('drawerBody').innerHTML='<div class="empty-state">Loading selected trace...</div>';
  openDrawer();
  var data;
  try{
    data=await api('/api/traces/'+encodeURIComponent(traceId)+'/map?slim=true');
  }catch(err){
    $('drawerBody').innerHTML='<div class="empty-state">Failed to load trace: '+esc(err.message||String(err))+'</div>';
    throw err;
  }
  var traceRoute=data.traces&&data.traces[0]&&data.traces[0].route_id;
  if(traceRoute&&(!routeState||!routeState.route||routeState.route.id!==traceRoute)){
    selectedRouteId=traceRoute;
    routeState=await api('/api/routes/'+encodeURIComponent(traceRoute)+'/requests?include_hidden=true');
  }
  selectedTraceId=traceId;
  if(traceRoute)switchTab('requests');
  renderTraceList();
  var flowLogs=data.flow_logs||data.logs||[];
  var backgroundLogs=data.nearby_background_logs||[];
  $('drawerTitle').textContent='Triggered map';
  $('drawerSub').textContent='trace '+traceId+' &bull; '+flowLogs.length+' exact logs &bull; '+(data.event_count||data.events.length)+' events &bull; '+data.dependencies.length+' dependency calls &bull; '+backgroundLogs.length+' nearby background logs hidden';
  var logsHtml=flowLogs.map(function(l){
    return '<div class="log-item"><div class="log-header"><span class="level-badge level-'+esc(l.level)+'">'+esc(l.level||'LOG')+'</span><span class="small">'+esc(l.service_name)+' &bull; '+esc(fmtTs(l.timestamp))+' &bull; exact trace</span></div><div class="log-body">'+esc(l.message)+'</div><div class="small mono">'+esc(l.logger_name||'')+(l.source_function?' &bull; '+esc(l.source_function):'')+'</div></div>';
  }).join('')||'<div class="empty-state">No logs directly correlated to this trace.</div>';
  var backgroundHtml=backgroundLogs.slice(0,80).map(function(l){
    return '<div class="log-item"><div class="log-header"><span class="level-badge level-'+esc(l.level)+'">'+esc(l.level||'LOG')+'</span><span class="small">'+esc(l.service_name)+' &bull; '+esc(fmtTs(l.timestamp))+' &bull; '+(l.trace_id?'other trace':'background/no trace')+'</span></div><div class="log-body">'+esc(l.message)+'</div><div class="small mono">'+esc(l.logger_name||'')+(l.source_function?' &bull; '+esc(l.source_function):'')+'</div></div>';
  }).join('');
  var hasGrouped=!!(data.flow&&Array.isArray(data.flow.nodes)&&data.flow.nodes.length);
  var groupedMap=renderMap(Object.assign({},data,{logs:flowLogs}));
  var rawTimeline=renderRawTimeline(data.timeline||data.events);
  $('drawerBody').innerHTML='<div class="tabs-row"><button class="btn btn-primary" data-copy-trace="'+esc(traceId)+'">Copy full trace for AI</button><span id="copyStatus" class="small copy-ok">Copy context is prepared only when requested.</span><span class="pill">'+data.traces.length+' route</span><span class="pill">'+data.spans.length+' spans</span><span class="pill">'+data.dependencies.length+' deps</span><span class="pill">'+flowLogs.length+' exact logs</span><span class="pill">'+data.exceptions.length+' errors</span></div><div class="explain">Only exact trace-id events are shown in the causal flow. Cron jobs, SQS pollers, and background tasks run independently with no trace id and are separated as nearby background activity.</div>'+renderTraceViewToggle(hasGrouped)+'<div id="groupedTraceView" class="trace-toggle-panel">'+groupedMap+'</div><div id="rawTraceView" class="trace-toggle-panel hidden-panel"><h3 style="margin:0 0 8px">Raw causal timeline</h3>'+rawTimeline+'</div><h3 style="margin:14px 0 8px">Dependency details + inputs</h3>'+renderDependencyDetails(data.dependencies||[])+'<h3 style="margin:14px 0 8px">Exact flow logs</h3><div>'+logsHtml+'</div>'+(hasGrouped?'':'<h3 style="margin:14px 0 8px">Raw causal timeline</h3>'+rawTimeline)+'<br><details style="margin-top:12px"><summary class="small" style="cursor:pointer;padding:4px 0">Nearby background activity ('+backgroundLogs.length+')</summary><div class="explain" style="margin-top:8px">These logs happened around the same time but have no matching trace_id.</div><div>'+(backgroundHtml||'<div class="empty-state">No nearby background logs.</div>')+'</div></details>';
  openDrawer();
}

// ── OPEN ERROR ──
async function openError(appId,id){
  var data=await api('/api/apps/'+encodeURIComponent(appId)+'/exceptions/'+encodeURIComponent(id)+'?include_context=false');
  if(data.exception&&data.exception.sample_trace_id){await openTraceMap(data.exception.sample_trace_id);return;}
  $('drawerTitle').textContent='Error';
  $('drawerSub').textContent=(data.exception&&data.exception.last_seen)||'';
  $('drawerBody').innerHTML='<pre>'+esc(pretty(data))+'</pre>';
  openDrawer();
}

// ── WIRE UP EVENT LISTENERS ──
$('refreshBtn').onclick=function(){withLoading(refresh);};
$('refreshInterval').onchange=function(e){setRefreshIntervalMs(e.target.value);};
$('logWindow').onchange=function(e){logWindowMinutes=Number(e.target.value);localStorage.setItem('runtimeObserverLogWindowMinutes',String(logWindowMinutes));withLoading(refresh);};
$('logSource').onchange=function(e){logSource=e.target.value;applyLocalLogFilters();};
syncLogWindowSelect();
$('searchBtn').onclick=function(){withLoading(searchLogs);};
$('level').onchange=function(){withLoading(searchLogs);};
$('logSearch').onkeydown=function(e){if(e.key==='Enter')withLoading(searchLogs);};
$('logSearch').oninput=applyLocalLogFilters;
$('routeSearch').oninput=function(e){routeSearchQuery=e.target.value;applyRouteSearch();};
$('showHiddenBtn').onclick=function(){showHidden=!showHidden;renderEntries();};
$('closeBtn').onclick=closeDrawer;
$('drawerFullscreenBtn').onclick=toggleDrawerFullscreen;
$('drawerOverlay').onclick=closeDrawer;
$('loginForm').onsubmit=loginSubmit;
$('logoutBtn').onclick=logout;
$('themeToggle').onclick=toggleTheme;
document.querySelectorAll('[data-tab]').forEach(function(b){b.onclick=function(){switchTab(b.dataset.tab);};});
document.addEventListener('click',function(ev){
  var depBtn=ev.target.closest('[data-copy-dep]');
  if(depBtn){ev.preventDefault();ev.stopPropagation();copyDependency(depBtn.dataset.copyDep,depBtn);return;}
  var traceBtn=ev.target.closest('[data-copy-trace]');
  if(traceBtn){ev.preventDefault();ev.stopPropagation();copyTrace(traceBtn.dataset.copyTrace,traceBtn);return;}
  var logBtn=ev.target.closest('[data-copy-log]');
  if(logBtn){ev.preventDefault();ev.stopPropagation();copyLog(logBtn.dataset.copyLog,logBtn);return;}
  var openTraceBtn=ev.target.closest('[data-open-trace]');
  if(openTraceBtn){ev.preventDefault();ev.stopPropagation();withLoading(function(){return openTraceMap(openTraceBtn.dataset.openTrace);});return;}
  var viewBtn=ev.target.closest('[data-trace-view]');
  if(viewBtn){
    ev.preventDefault();ev.stopPropagation();
    var showRaw=viewBtn.dataset.traceView==='raw';
    if($('groupedTraceView'))$('groupedTraceView').classList.toggle('hidden-panel',showRaw);
    if($('rawTraceView'))$('rawTraceView').classList.toggle('hidden-panel',!showRaw);
    document.querySelectorAll('[data-trace-view]').forEach(function(btn){btn.classList.toggle('btn-primary',btn===viewBtn);});
  }
});

// ── EXPOSE GLOBALS NEEDED BY INLINE ONCLICK HANDLERS ──
window.backToProjects = backToProjects;
window.createProjectKey = function(name){return withLoading(function(){return createProjectKey(name);});};
window.openTraceMap = function(traceId){return withLoading(function(){return openTraceMap(traceId);});};

// ── INIT ──
checkAuth().then(function(ok){
  if(ok){setRefreshIntervalMs($('refreshInterval').value);refresh();}
});

})();
</script></body></html>
'''
