from __future__ import annotations


DASHBOARD_HTML = r'''<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Runtime Observer</title>
<link rel="icon" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a3e635' stroke-width='2'><circle cx='12' cy='12' r='3'/><circle cx='12' cy='12' r='9'/><path d='M12 3v3M12 18v3M3 12h3M18 12h3'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@500;600;700&display=swap" rel="stylesheet">
<style>
/* ─────────────────────────  TOKENS  ───────────────────────── */
[data-theme="dark"]{
  --bg:#0a0b0d; --bg-2:#0e1014; --panel:#11141a; --panel-2:#161a22;
  --ink:#e6ebf2; --muted:#7c8898; --dim:#4a5462; --faint:#2a3140;
  --rule:#1c2230; --rule-2:#252d3d;
  --signal:#a3e635; --signal-2:#84cc16; --signal-soft:rgba(163,230,53,.12);
  --good:#4ade80; --warn:#fbbf24; --bad:#f87171; --info:#60a5fa;
  --good-soft:rgba(74,222,128,.12); --warn-soft:rgba(251,191,36,.12); --bad-soft:rgba(248,113,113,.12); --info-soft:rgba(96,165,250,.12);
}
[data-theme="light"]{
  --bg:#f6f7f5; --bg-2:#eef0ec; --panel:#ffffff; --panel-2:#fafbf8;
  --ink:#121417; --muted:#5b6470; --dim:#8a93a0; --faint:#c5cbd4;
  --rule:#e2e6e0; --rule-2:#d2d7cf;
  --signal:#4d7c0f; --signal-2:#65a30d; --signal-soft:rgba(101,163,13,.12);
  --good:#16a34a; --warn:#b45309; --bad:#b91c1c; --info:#1d4ed8;
  --good-soft:rgba(22,163,74,.10); --warn-soft:rgba(180,83,9,.10); --bad-soft:rgba(185,28,28,.10); --info-soft:rgba(29,78,216,.10);
}
:root{
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:"Inter",ui-sans-serif,system-ui,-apple-system,sans-serif;
  --rail-w:56px;
  --rail-w-expanded:188px;
  --top-h:48px;
  --sub-h:38px;
}

/* ─────────────────────────  RESET  ───────────────────────── */
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100vh;overflow:hidden;background:var(--bg);color:var(--ink)}
body{font-family:var(--mono);font-size:12.5px;line-height:1.5;-webkit-font-smoothing:antialiased;font-feature-settings:"tnum","ss01";cursor:default}
body.loading,body.loading *{cursor:wait!important}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
input,select,textarea{font:inherit;color:inherit}
a{color:inherit;text-decoration:none}
::selection{background:var(--signal);color:#0a0b0d}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--rule-2);border-radius:0}
::-webkit-scrollbar-thumb:hover{background:var(--dim)}

/* ─────────────────────────  SHELL  ───────────────────────── */
#shell{height:100vh;display:grid;grid-template-rows:var(--top-h) var(--sub-h) 1fr;grid-template-columns:var(--rail-w) 1fr;grid-template-areas:"top top" "sub sub" "rail main";transition:grid-template-columns .18s ease}
#shell.rail-expanded{grid-template-columns:var(--rail-w-expanded) 1fr}
#shell.no-project{grid-template-rows:var(--top-h) 1fr;grid-template-columns:1fr;grid-template-areas:"top" "main"}
.topbar{grid-area:top;display:flex;align-items:center;gap:0;height:var(--top-h);background:var(--bg);border-bottom:1px solid var(--rule);position:relative;z-index:30}
.subbar{grid-area:sub;height:var(--sub-h);background:var(--bg-2);border-bottom:1px solid var(--rule);display:flex;align-items:center;gap:0;padding:0 14px;position:relative;z-index:25}
.rail{grid-area:rail;background:var(--bg);border-right:1px solid var(--rule);display:flex;flex-direction:column;align-items:stretch}
.main{grid-area:main;overflow:hidden;background:var(--bg);display:flex;flex-direction:column;min-width:0}

/* ─────────────────────────  TOPBAR  ───────────────────────── */
.brand{display:flex;align-items:center;gap:10px;padding:0 16px;height:100%;border-right:1px solid var(--rule);min-width:var(--rail-w);justify-content:center;cursor:pointer;transition:background .1s,color .1s}
.brand:hover .brand-name{color:var(--signal)}
.brand:hover .brand-mark{filter:brightness(1.15)}
.brand-mark{width:20px;height:20px;color:var(--signal);flex:none}
.brand-name{font-family:var(--sans);font-size:13px;font-weight:700;letter-spacing:.01em;display:none}
@media(min-width:900px){.brand{padding:0 18px;justify-content:flex-start;min-width:auto}.brand-name{display:inline}}
.crumbs{display:flex;align-items:center;gap:0;height:100%;flex:1;min-width:0;overflow:hidden}
.crumb{height:100%;padding:0 14px;display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--muted);border-right:1px solid var(--rule);cursor:pointer;transition:background .1s,color .1s;white-space:nowrap;letter-spacing:.02em;text-transform:uppercase;flex:none}
.crumb:hover{color:var(--ink);background:var(--panel)}
.crumb .key{color:var(--dim);font-weight:500}
.crumb .val{color:var(--ink);font-weight:600}
.crumb .chev{color:var(--dim);font-size:10px;margin-left:6px}
.crumb-disabled{color:var(--dim);cursor:default}
.crumb-disabled:hover{background:transparent;color:var(--dim)}
.top-spacer{flex:1}
.top-actions{display:flex;align-items:center;gap:0;height:100%}
.top-actions .item{height:100%;padding:0 12px;display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);border-left:1px solid var(--rule);text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.top-actions button.item{transition:color .1s,background .1s}
.top-actions button.item:hover{color:var(--ink);background:var(--panel)}
.live-dot{width:7px;height:7px;background:var(--signal);border-radius:50%;flex:none;box-shadow:0 0 0 0 var(--signal)}
.live-dot.pulsing{animation:pulse 1.8s ease-in-out infinite}
.live-dot.paused{background:var(--dim);animation:none}
.live-dot.error{background:var(--bad);animation:none}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(163,230,53,.6)}50%{box-shadow:0 0 0 5px rgba(163,230,53,0)}}
.user-chip{display:flex;align-items:center;gap:6px;color:var(--muted)}
.user-chip .who{color:var(--ink);font-weight:600}
.env-badge{font-size:10px;font-weight:700;padding:2px 7px;border:1px solid var(--rule-2);color:var(--signal);background:var(--signal-soft);letter-spacing:.06em}

/* ─────────────────────────  SUBBAR (filters)  ───────────────────────── */
.sb-group{display:flex;align-items:center;gap:8px;height:100%;padding-right:14px;border-right:1px solid var(--rule);margin-right:14px}
.sb-group:last-of-type{border-right:0}
.sb-label{font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--dim);font-weight:600}
.sb-select{appearance:none;-webkit-appearance:none;background:var(--panel);border:1px solid var(--rule-2);color:var(--ink);padding:4px 22px 4px 8px;font-size:11.5px;border-radius:0;cursor:pointer;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 12px) 50%,calc(100% - 8px) 50%;background-size:4px 4px,4px 4px;background-repeat:no-repeat;transition:border-color .1s}
.sb-select:hover{border-color:var(--signal)}
.sb-select:focus{outline:none;border-color:var(--signal)}
.sb-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;font-size:11px;color:var(--muted);border:1px solid var(--rule-2);background:var(--panel);text-transform:uppercase;letter-spacing:.06em;font-weight:600;transition:all .1s}
.sb-pill:hover{color:var(--ink);border-color:var(--signal)}
.sb-pill.active{color:var(--signal);border-color:var(--signal);background:var(--signal-soft)}
.sb-input{background:var(--panel);border:1px solid var(--rule-2);color:var(--ink);padding:4px 8px;font-size:11.5px;border-radius:0;min-width:200px;transition:border-color .1s}
.sb-input:focus{outline:none;border-color:var(--signal)}
.sb-input::placeholder{color:var(--dim)}

/* ─────────────────────────  RAIL (left nav)  ───────────────────────── */
.rail-btn{height:48px;display:flex;align-items:center;justify-content:center;color:var(--dim);border-left:2px solid transparent;border-bottom:1px solid var(--rule);transition:color .1s,background .1s,border-color .1s,padding .18s ease,gap .18s ease;position:relative}
.rail-btn:hover{color:var(--ink);background:var(--panel)}
.rail-btn.active{color:var(--signal);border-left-color:var(--signal);background:var(--signal-soft)}
.rail-btn svg{width:16px;height:16px;stroke-width:1.8;flex:none}
.rail-btn .badge{position:absolute;top:8px;right:8px;background:var(--bad);color:#fff;font-size:9px;font-weight:700;padding:1px 4px;min-width:14px;text-align:center;border-radius:0}
.rail-btn .tip{position:absolute;left:calc(100% + 8px);top:50%;transform:translateY(-50%);background:var(--panel);border:1px solid var(--rule-2);padding:5px 9px;font-size:11px;color:var(--ink);white-space:nowrap;text-transform:uppercase;letter-spacing:.06em;opacity:0;pointer-events:none;transition:opacity .12s;z-index:50}
.rail-btn:hover .tip{opacity:1}
.rail.expanded .rail-btn{justify-content:flex-start;padding:0 16px;gap:14px}
.rail.expanded .rail-btn .tip{position:static;background:none;border:0;padding:0;opacity:1;pointer-events:auto;transform:none;color:inherit;font-size:11px;letter-spacing:.08em;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rail.expanded .rail-btn .badge{top:50%;right:14px;transform:translateY(-50%)}
.rail-spacer{flex:1}
#shell.rail-expanded .brand{min-width:var(--rail-w-expanded);justify-content:flex-start;padding:0 18px}

/* ─────────────────────────  PAGE  ───────────────────────── */
.page{height:100%;overflow-y:auto;overflow-x:hidden;padding:0;display:flex;flex-direction:column}
.page-header{padding:18px 24px 14px;display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex:none}
.page-title{font-family:var(--sans);font-size:18px;font-weight:700;letter-spacing:-.01em;color:var(--ink)}
.page-sub{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
.page-actions{display:flex;gap:8px;align-items:center}
.page-body{padding:0 24px 24px;flex:1;min-height:0}

/* ─────────────────────────  PANEL / RULE  ───────────────────────── */
.panel{background:var(--panel);border:1px solid var(--rule);margin-bottom:14px}
.panel-head{padding:8px 14px;border-bottom:1px solid var(--rule);display:flex;align-items:center;justify-content:space-between;gap:10px;background:var(--bg-2)}
.panel-title{font-size:10.5px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-weight:700}
.panel-meta{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em}
.panel-body{padding:14px}
.panel-body.no-pad{padding:0}
.hr{height:1px;background:var(--rule);margin:14px 0}

/* ─────────────────────────  VITAL STRIP  ───────────────────────── */
.vitals{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--rule);background:var(--panel);margin-bottom:14px}
@media(max-width:1100px){.vitals{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.vitals{grid-template-columns:repeat(2,1fr)}}
.vital{padding:14px 16px;border-right:1px solid var(--rule);position:relative;display:flex;flex-direction:column;gap:4px;min-width:0}
.vital:last-child{border-right:0}
.vital .v-label{font-size:9.5px;text-transform:uppercase;letter-spacing:.16em;color:var(--dim);font-weight:600}
.vital .v-num{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--ink);line-height:1.1;letter-spacing:-.01em}
.vital .v-sub{font-size:10.5px;color:var(--muted);display:flex;align-items:center;gap:6px}
.vital .v-spark{height:18px;margin-top:4px;display:flex;align-items:flex-end;gap:1px}
.vital .v-spark span{flex:1;min-width:2px;background:var(--signal);opacity:.55;min-height:2px;transition:opacity .1s}
.vital .v-spark.err span{background:var(--bad)}
.vital .v-spark.warn span{background:var(--warn)}
.vital.alert .v-num{color:var(--bad)}
.vital.warn .v-num{color:var(--warn)}
.delta-up{color:var(--good)}
.delta-down{color:var(--bad)}
.delta-flat{color:var(--dim)}

/* ─────────────────────────  STATUS CHIP  ───────────────────────── */
.chip{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--rule-2);background:var(--bg-2);color:var(--muted)}
.chip.good{color:var(--good);border-color:var(--good);background:var(--good-soft)}
.chip.warn{color:var(--warn);border-color:var(--warn);background:var(--warn-soft)}
.chip.bad{color:var(--bad);border-color:var(--bad);background:var(--bad-soft)}
.chip.info{color:var(--info);border-color:var(--info);background:var(--info-soft)}
.chip.signal{color:var(--signal);border-color:var(--signal);background:var(--signal-soft)}
.chip.dim{color:var(--dim);border-color:var(--rule-2)}

.method{display:inline-flex;align-items:center;padding:1px 6px;font-size:10px;font-weight:700;letter-spacing:.06em;border:1px solid currentColor;flex:none}
.method-GET{color:var(--good)}
.method-POST{color:var(--info)}
.method-PUT,.method-PATCH{color:var(--warn)}
.method-DELETE{color:var(--bad)}
.method-OTHER{color:var(--signal)}

/* ─────────────────────────  TABLE  ───────────────────────── */
.tbl{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px}
.tbl thead th{position:sticky;top:0;background:var(--bg-2);text-align:left;padding:7px 12px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);font-weight:600;border-bottom:1px solid var(--rule);user-select:none;cursor:default;white-space:nowrap}
.tbl thead th.sortable{cursor:pointer;transition:color .1s}
.tbl thead th.sortable:hover{color:var(--ink)}
.tbl thead th.sortable .arr{display:inline-block;width:8px;margin-left:4px;color:var(--signal)}
.tbl tbody td{padding:8px 12px;border-bottom:1px solid var(--rule);color:var(--ink);vertical-align:middle;max-width:0}
.tbl tbody tr{transition:background .08s}
.tbl tbody tr:hover{background:var(--bg-2)}
.tbl tbody tr.row-clickable{cursor:pointer}
.tbl tbody tr.row-clickable:hover{background:var(--signal-soft)}
.tbl td.num,.tbl th.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl td.dim{color:var(--muted)}
.tbl td.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:0}
.tbl td .sub{font-size:10.5px;color:var(--dim);margin-top:2px}
.tbl td.status-cell,.tbl td.action-cell{max-width:none;width:1%;white-space:nowrap}
.tbl td.action-cell{text-align:right}
.tbl-wrap{overflow-x:auto}

.pager{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-top:1px solid var(--rule);background:var(--bg-2);font-size:11px;color:var(--muted)}
.pager .left,.pager .right{display:flex;align-items:center;gap:8px}
.pager button{padding:3px 8px;border:1px solid var(--rule-2);color:var(--muted);transition:all .1s;background:var(--panel);text-transform:uppercase;font-size:10px;letter-spacing:.06em}
.pager button:hover:not(:disabled){color:var(--ink);border-color:var(--signal)}
.pager button:disabled{opacity:.35;cursor:not-allowed}

/* ─────────────────────────  ATTENTION / STREAM  ───────────────────────── */
.stream{display:flex;flex-direction:column}
.stream-row{display:grid;grid-template-columns:80px 50px 1fr auto;gap:14px;padding:9px 14px;border-bottom:1px solid var(--rule);align-items:center;cursor:pointer;transition:background .08s;font-size:12px}
.stream-row:hover{background:var(--bg-2)}
.stream-row:last-child{border-bottom:0}
.stream-row .when{color:var(--dim);font-size:11px;font-variant-numeric:tabular-nums}
.stream-row .what{color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stream-row .meta{color:var(--muted);font-size:11px;text-align:right;white-space:nowrap}

/* ─────────────────────────  TRACE WATERFALL  ───────────────────────── */
.split{display:grid;gap:0;height:100%;min-height:0}
.split.t-list{grid-template-columns:minmax(360px,420px) 1fr;border-top:1px solid var(--rule)}
.split.t-list .col{overflow:hidden;display:flex;flex-direction:column;min-height:0;min-width:0}
.split.t-list .col:first-child{border-right:1px solid var(--rule)}
.split.t-list-3col{grid-template-columns:minmax(220px,260px) minmax(320px,380px) 1fr;border-top:1px solid var(--rule);transition:grid-template-columns .18s ease}
.split.t-list-3col.r-collapsed{grid-template-columns:34px minmax(320px,380px) 1fr}
.split.t-list-3col.c-collapsed{grid-template-columns:minmax(220px,260px) 34px 1fr}
.split.t-list-3col.r-collapsed.c-collapsed{grid-template-columns:34px 34px 1fr}
.split.t-list-3col .col{overflow:hidden;display:flex;flex-direction:column;min-height:0;min-width:0}
.split.t-list-3col .col:nth-child(1),
.split.t-list-3col .col:nth-child(2){border-right:1px solid var(--rule)}

.trace-row{display:grid;grid-template-columns:42px 1fr 60px;gap:10px;padding:10px 12px;border-bottom:1px solid var(--rule);align-items:center;cursor:pointer;transition:background .08s}
.trace-row:hover{background:var(--bg-2)}
.trace-row.active{background:var(--signal-soft);border-left:2px solid var(--signal);padding-left:10px}
.trace-row .status{font-size:11px;font-weight:700;text-align:center}
.trace-row .status.ok{color:var(--good)}
.trace-row .status.err{color:var(--bad)}
.trace-row .route{font-size:12px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trace-row .route .method{margin-right:6px}
.trace-row .meta{font-size:10.5px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trace-row .dur{font-size:12px;color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}

/* trace-page sidebars (routes + calls) */
.t-sidebar{background:var(--bg)}
.t-side-head{padding:8px 10px;border-bottom:1px solid var(--rule);flex:none;background:var(--bg-2);display:flex;align-items:center;gap:6px}
.t-side-head .t-side-search{flex:1;min-width:0}
.t-collapse-btn{flex:none;width:22px;height:22px;display:flex;align-items:center;justify-content:center;color:var(--muted);border:1px solid var(--rule-2);background:var(--panel);transition:all .1s;font-size:13px;line-height:1;font-family:var(--mono)}
.t-collapse-btn:hover{color:var(--signal);border-color:var(--signal)}
.t-collapsed-rail{display:flex;flex-direction:column;align-items:center;padding:8px 0;cursor:pointer;height:100%;background:var(--bg-2);transition:background .1s;gap:10px}
.t-collapsed-rail:hover{background:var(--panel)}
.t-collapsed-rail:hover .t-collapsed-ico,
.t-collapsed-rail:hover .t-collapsed-label{color:var(--signal)}
.t-collapsed-ico{color:var(--muted);font-size:13px;font-family:var(--mono);transition:color .1s;line-height:1}
.t-collapsed-label{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10px;text-transform:uppercase;letter-spacing:.18em;color:var(--dim);font-weight:600;transition:color .1s;white-space:nowrap}
.t-collapsed-count{font-size:10px;color:var(--dim);font-variant-numeric:tabular-nums;margin-top:auto;padding-bottom:6px}
.t-side-search{width:100%;background:var(--panel);border:1px solid var(--rule-2);color:var(--ink);padding:5px 8px;font-size:11.5px;font-family:var(--mono);border-radius:0;transition:border-color .1s}
.t-side-search:focus{outline:none;border-color:var(--signal)}
.t-side-search::placeholder{color:var(--dim)}
.t-side-search:disabled{opacity:.45;cursor:not-allowed}
.t-side-list{flex:1;min-height:0;overflow-y:auto}
.error-cluster-list{flex:1;min-height:0;overflow-y:auto}
.t-side-row{padding:8px 12px;border-bottom:1px solid var(--rule);cursor:pointer;transition:background .08s;display:flex;flex-direction:column;gap:3px;border-left:2px solid transparent}
.t-side-row:hover{background:var(--bg-2)}
.t-side-row.active{background:var(--signal-soft);border-left-color:var(--signal)}
.t-side-row-line{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--ink);min-width:0}
.t-side-row-line .truncate{flex:1;min-width:0}
.t-side-row-meta{display:flex;align-items:center;justify-content:space-between;font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums;gap:8px}
.t-side-pager{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-top:1px solid var(--rule);background:var(--bg-2);font-size:10.5px;color:var(--muted);flex:none;gap:8px}
.t-pager-btn{padding:2px 9px;border:1px solid var(--rule-2);color:var(--muted);background:var(--panel);font-size:13px;line-height:1;transition:all .1s;font-family:var(--mono)}
.t-pager-btn:hover:not(:disabled){color:var(--signal);border-color:var(--signal)}
.t-pager-btn:disabled{opacity:.35;cursor:not-allowed}
.t-pager-info{font-variant-numeric:tabular-nums;text-align:center;flex:1;text-transform:uppercase;letter-spacing:.06em;font-size:10px}

.waterfall{padding:14px;overflow-y:auto;height:100%}
.wf-head{display:grid;grid-template-columns:1fr;gap:6px;padding-bottom:12px;border-bottom:1px solid var(--rule);margin-bottom:12px}
.wf-title{font-family:var(--sans);font-size:15px;font-weight:600;color:var(--ink);display:flex;align-items:center;gap:10px}
.wf-meta{display:flex;flex-wrap:wrap;gap:14px;font-size:11px;color:var(--muted)}
.wf-meta .kv{display:flex;align-items:center;gap:6px}
.wf-meta .kv .k{color:var(--dim);text-transform:uppercase;letter-spacing:.06em;font-size:10px}
.wf-meta .kv .v{color:var(--ink);font-variant-numeric:tabular-nums}
.wf-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.wf-tabs{display:flex;gap:0;border-bottom:1px solid var(--rule);margin-bottom:12px}
.wf-tab{padding:6px 12px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .1s,border-color .1s}
.wf-tab:hover{color:var(--ink)}
.wf-tab.active{color:var(--signal);border-bottom-color:var(--signal)}

.wf-bars{display:flex;flex-direction:column;gap:1px}
.wf-bar{display:grid;grid-template-columns:56px minmax(180px,280px) minmax(120px,1fr) 64px;gap:10px;padding:5px 0;align-items:center;font-size:11px;border-bottom:1px solid var(--rule);cursor:pointer;transition:background .08s}
.wf-bar:hover{background:var(--bg-2)}
.wf-bar:focus-visible{outline:1px solid var(--signal);outline-offset:-1px;background:var(--bg-2)}
.wf-bar.is-open{background:var(--bg-2)}
.wf-bar .offset{color:var(--dim);font-variant-numeric:tabular-nums;text-align:right;padding-right:4px;border-right:1px solid var(--rule)}
.wf-bar .name{display:flex;align-items:center;gap:6px;color:var(--ink);min-width:0}
.wf-bar .name .indent{flex:none;color:var(--dim);font-family:var(--mono)}
.wf-bar .name .label-col{display:flex;flex-direction:column;gap:1px;min-width:0;flex:1}
.wf-bar .name .label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-variant-numeric:tabular-nums}
.wf-bar .name .sublabel{font-size:10px;color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--mono)}
.wf-bar .name .kind{font-size:9px;padding:1px 4px;border:1px solid currentColor;letter-spacing:.06em;text-transform:uppercase;flex:none}
.wf-bar .name .kind.http{color:var(--info)}
.wf-bar .name .kind.db{color:var(--good)}
.wf-bar .name .kind.llm{color:var(--signal)}
.wf-bar .name .kind.queue{color:var(--warn)}
.wf-bar .name .kind.error{color:var(--bad)}
.wf-bar .name .kind.span{color:var(--muted)}
.wf-bar .track{position:relative;background:var(--bg-2);height:14px;border:1px solid var(--rule)}
.wf-bar .fill{position:absolute;top:0;bottom:0;background:var(--signal);min-width:2px}
.wf-bar .fill.http{background:var(--info)}
.wf-bar .fill.db{background:var(--good)}
.wf-bar .fill.llm{background:var(--signal-2)}
.wf-bar .fill.error{background:var(--bad);width:3px!important;min-width:3px}
.wf-bar .dur{text-align:right;color:var(--ink);font-variant-numeric:tabular-nums}
.wf-row-detail{padding:12px 14px;background:var(--bg-2);border-bottom:1px solid var(--rule);font-family:var(--mono);font-size:11.5px;color:var(--ink);max-height:520px;overflow:auto}
.wf-row-detail .kvline{display:flex;gap:10px;margin-bottom:6px;white-space:nowrap}
.wf-row-detail .kvline .k{color:var(--dim);text-transform:uppercase;letter-spacing:.06em;font-size:10px;min-width:80px;flex:none}
.wf-row-detail .kvline .v{color:var(--ink);flex:1;white-space:pre-wrap;word-break:break-word}
.wf-row-detail pre{margin:0;background:var(--bg);padding:8px;border:1px solid var(--rule);white-space:pre-wrap;word-break:break-word}
.sql-block{margin:10px 0;border:1px solid var(--rule);background:var(--bg)}
.sql-block:first-child{margin-top:4px}
.sql-block .sql-head{display:flex;align-items:center;justify-content:space-between;padding:5px 10px;background:var(--bg-2);border-bottom:1px solid var(--rule)}
.sql-block .sql-label{color:var(--dim);text-transform:uppercase;letter-spacing:.08em;font-size:10px;font-weight:600}
.sql-block .sql-pre{margin:0;padding:10px 12px;background:var(--bg);border:0;font-family:var(--mono);font-size:12px;line-height:1.5;color:var(--ink);white-space:pre-wrap;word-break:break-word;max-height:340px;overflow:auto}
.tbl tbody td.dep-chev{padding:8px 0 8px 12px;color:var(--dim);width:24px}
.tbl tbody td.dep-chev .chev{display:inline-block;width:12px;font-size:10px;color:var(--muted);transition:transform .1s}
.tbl tbody tr.is-open td.dep-chev .chev{color:var(--signal)}
.tbl-dep tbody tr.dep-detail-row:hover{background:var(--bg-2)}

/* time axis ticks */
.wf-axis{display:grid;grid-template-columns:56px minmax(180px,280px) minmax(120px,1fr) 64px;gap:10px;font-size:9.5px;color:var(--dim);padding:0 0 4px;border-bottom:1px solid var(--rule);margin-bottom:4px;font-variant-numeric:tabular-nums}
.wf-axis .ticks{position:relative;height:14px}
.wf-axis .ticks span{position:absolute;top:0;transform:translateX(-50%);white-space:nowrap}

/* ─────────────────────────  LOGS  ───────────────────────── */
.log-row{display:grid;grid-template-columns:130px 60px 130px 1fr;gap:14px;padding:7px 14px;border-bottom:1px solid var(--rule);align-items:start;font-size:11.5px;cursor:pointer;transition:background .08s}
.log-row:hover{background:var(--bg-2)}
.log-row .ts{color:var(--dim);font-variant-numeric:tabular-nums;white-space:nowrap}
.log-row .lvl{font-weight:700;font-size:10px;letter-spacing:.06em;text-transform:uppercase;text-align:left}
.log-row .lvl.INFO{color:var(--info)}
.log-row .lvl.WARNING,.log-row .lvl.WARN{color:var(--warn)}
.log-row .lvl.ERROR,.log-row .lvl.CRITICAL{color:var(--bad)}
.log-row .lvl.DEBUG{color:var(--dim)}
.log-row .svc{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.log-row .msg{color:var(--ink);overflow:hidden;word-break:break-word}
.log-row .msg .lname{color:var(--dim);font-size:10.5px;margin-top:2px}

/* ─────────────────────────  STACK FRAMES  ───────────────────────── */
.stack-frames{display:flex;flex-direction:column;border:1px solid var(--rule);background:var(--panel)}
.stack-frame{display:grid;grid-template-columns:24px 1fr auto;gap:10px;padding:8px 12px;border-bottom:1px solid var(--rule);font-family:var(--mono);font-size:11.5px;align-items:start}
.stack-frame:last-child{border-bottom:0}
.stack-frame.vendor{color:var(--dim);background:transparent}
.stack-frame.user{background:var(--bg-2)}
.stack-frame .num{color:var(--dim);font-variant-numeric:tabular-nums;text-align:right;font-size:10.5px;padding-top:1px}
.stack-frame .body{min-width:0}
.stack-frame .fn{color:var(--ink);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stack-frame.vendor .fn{color:var(--muted);font-weight:400}
.stack-frame .loc{color:var(--dim);font-size:10.5px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stack-frame .badge{font-size:9px;color:var(--muted);border:1px solid currentColor;padding:1px 5px;letter-spacing:.06em;text-transform:uppercase;align-self:start;font-family:var(--mono);white-space:nowrap}
.stack-frame.user .badge{color:var(--signal)}
.err-detail{display:flex;flex-direction:column;gap:14px}
.err-message{font-family:var(--mono);font-size:12px;color:var(--ink);background:var(--bg-2);border:1px solid var(--rule);padding:10px 12px;white-space:pre-wrap;word-break:break-word;max-height:240px;overflow:auto}
.err-message.error{border-left:3px solid var(--bad)}
.err-timeline{display:flex;flex-direction:column;gap:1px}
.err-timeline-row{display:grid;grid-template-columns:90px 60px 1fr auto;gap:10px;padding:6px 10px;border-bottom:1px solid var(--rule);font-family:var(--mono);font-size:11px;align-items:center;cursor:pointer;transition:background .08s}
.err-timeline-row:hover{background:var(--bg-2)}
.err-timeline-row.is-error{background:var(--bad-soft);border-left:3px solid var(--bad);padding-left:7px}
.err-timeline-row .ts{color:var(--dim);font-variant-numeric:tabular-nums;text-align:right}
.err-timeline-row .kind{font-size:9px;padding:1px 5px;border:1px solid currentColor;letter-spacing:.06em;text-transform:uppercase}
.err-timeline-row .kind.db{color:var(--good)}
.err-timeline-row .kind.http{color:var(--info)}
.err-timeline-row .kind.span{color:var(--muted)}
.err-timeline-row .kind.fn{color:var(--muted)}
.err-timeline-row .kind.log{color:var(--info)}
.err-timeline-row .kind.error{color:var(--bad)}
.err-timeline-row .desc{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink)}
.err-timeline-row .dur{color:var(--dim);font-variant-numeric:tabular-nums;font-size:10.5px}

/* ─────────────────────────  EMPTY / LOADING  ───────────────────────── */
.empty{padding:40px 24px;text-align:center;color:var(--muted);border:1px dashed var(--rule-2);background:var(--bg-2)}
.empty .ico{font-size:22px;color:var(--dim);margin-bottom:8px;font-weight:700;letter-spacing:.2em}
.empty p{font-size:12px;line-height:1.6;max-width:42ch;margin:0 auto 12px}
.empty .hint{font-size:11px;color:var(--dim)}

.spinner{display:inline-block;width:10px;height:10px;border:1.5px solid var(--dim);border-top-color:var(--signal);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* ─────────────────────────  BUTTONS  ───────────────────────── */
.btn{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;font-size:11px;font-weight:600;color:var(--muted);background:var(--panel);border:1px solid var(--rule-2);text-transform:uppercase;letter-spacing:.06em;transition:all .1s}
.btn:hover:not(:disabled){color:var(--ink);border-color:var(--signal)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-primary{color:#0a0b0d;background:var(--signal);border-color:var(--signal)}
.btn-primary:hover:not(:disabled){background:var(--signal-2);border-color:var(--signal-2);color:#0a0b0d}
.btn-danger{color:var(--bad);border-color:var(--bad)}
.btn-danger:hover{background:var(--bad-soft);color:var(--bad)}
.btn-sm{padding:3px 7px;font-size:10px}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;color:var(--muted);background:transparent;border:1px solid var(--rule-2);transition:all .1s}
.icon-btn:hover{color:var(--signal);border-color:var(--signal)}
.icon-btn svg{width:13px;height:13px;stroke-width:1.8}

/* ─────────────────────────  CHARTS  ───────────────────────── */
.timeline{background:var(--panel);border:1px solid var(--rule);padding:14px}
.timeline-svg{width:100%;height:120px;display:block}
.timeline-svg .grid{stroke:var(--rule);stroke-width:.5}
.timeline-svg .axis{stroke:var(--rule-2);stroke-width:.5}
.timeline-svg .axis-text{fill:var(--dim);font-size:9px;font-family:var(--mono)}
.timeline-svg .area-req{fill:var(--signal);fill-opacity:.18}
.timeline-svg .line-req{fill:none;stroke:var(--signal);stroke-width:1.4}
.timeline-svg .area-err{fill:var(--bad);fill-opacity:.25}
.timeline-svg .line-err{fill:none;stroke:var(--bad);stroke-width:1.4}
.timeline-legend{display:flex;gap:18px;margin-top:8px;font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.timeline-legend .sw{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px}

/* ─────────────────────────  DRAWER (for AI-copy + key creation only)  ───────────────────────── */
.drawer-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:90;display:none}
.drawer-overlay.open{display:block}
.drawer{position:fixed;right:0;top:0;bottom:0;width:min(720px,95vw);background:var(--bg);border-left:1px solid var(--rule-2);transform:translateX(105%);transition:transform .22s cubic-bezier(.2,.7,.2,1);z-index:91;display:flex;flex-direction:column}
.drawer.open{transform:translateX(0)}
.drawer-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px 18px;border-bottom:1px solid var(--rule);flex:none}
.drawer-title{font-family:var(--sans);font-size:14px;font-weight:600;color:var(--ink)}
.drawer-sub{font-size:11px;color:var(--muted);margin-top:2px}
.drawer-body{padding:14px 18px;overflow-y:auto;flex:1}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg-2);border:1px solid var(--rule);padding:10px;font-size:11.5px;font-family:var(--mono);max-height:50vh;overflow:auto;color:var(--ink)}

/* ─────────────────────────  LOGIN  ───────────────────────── */
.login-overlay{position:fixed;inset:0;z-index:100;display:grid;place-items:center;background:rgba(10,11,13,.96);backdrop-filter:blur(8px)}
.login-box{width:min(380px,90vw);background:var(--panel);border:1px solid var(--rule-2);padding:28px}
.login-brand{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.login-brand svg{color:var(--signal)}
.login-brand .name{font-family:var(--sans);font-size:14px;font-weight:700}
.login-title{font-family:var(--sans);font-size:20px;font-weight:700;color:var(--ink);margin:18px 0 4px}
.login-hint{font-size:11.5px;color:var(--muted);margin-bottom:20px}
.login-form{display:flex;flex-direction:column;gap:10px}
.form-input{background:var(--bg-2);border:1px solid var(--rule-2);padding:9px 12px;font-size:12.5px;color:var(--ink);font-family:var(--mono);transition:border-color .1s}
.form-input:focus{outline:none;border-color:var(--signal)}
.form-input::placeholder{color:var(--dim)}
.login-err{font-size:11.5px;color:var(--bad);min-height:16px}

/* ─────────────────────────  PROJECT SCREEN  ───────────────────────── */
.proj-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.proj-toggle{display:inline-flex;border:1px solid var(--rule-2);background:var(--panel);padding:2px}
.proj-toggle button{padding:4px 10px;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);transition:color .1s,background .1s}
.proj-toggle button.active{background:var(--signal);color:#0a0b0d}
.proj-filter{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.proj-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin-top:14px}
.proj-card{background:var(--panel);border:1px solid var(--rule);padding:18px;cursor:pointer;transition:border-color .1s,background .1s}
.proj-card:hover{border-color:var(--signal);background:var(--panel-2)}
.proj-card .proj-name{font-family:var(--sans);font-size:15px;font-weight:700;color:var(--ink);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.proj-card .proj-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:10px 0}
.proj-card .ps{display:flex;flex-direction:column;gap:2px}
.proj-card .ps .num{font-size:18px;font-weight:600;color:var(--ink);font-variant-numeric:tabular-nums}
.proj-card .ps .lbl{font-size:9.5px;text-transform:uppercase;letter-spacing:.12em;color:var(--dim)}
.proj-card .proj-meta{font-size:10.5px;color:var(--muted);margin-bottom:10px;display:flex;flex-direction:column;gap:2px}
.proj-card .proj-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid var(--rule)}

/* ─────────────────────────  ROUTE LIST PILLS (inside Routes/Traces)  ───────────────────────── */
.filter-row{display:flex;gap:6px;align-items:center;flex-wrap:nowrap;padding:0 14px 12px;margin-top:-2px;overflow-x:auto;overflow-y:hidden;scrollbar-width:thin;max-height:46px;flex:none}
.filter-row::-webkit-scrollbar{height:6px}
.filter-row.wrap{flex-wrap:wrap;max-height:none;overflow:visible}
.filter-row .sb-pill{flex:none}

/* ─────────────────────────  UTILITY  ───────────────────────── */
.hidden{display:none!important}
.mono{font-family:var(--mono)}
.sans{font-family:var(--sans)}
.tnum{font-variant-numeric:tabular-nums}
.txt-dim{color:var(--dim)}
.txt-muted{color:var(--muted)}
.txt-bad{color:var(--bad)}
.txt-good{color:var(--good)}
.txt-warn{color:var(--warn)}
.txt-signal{color:var(--signal)}
.flex{display:flex}
.flex-1{flex:1}
.gap-1{gap:4px}
.gap-2{gap:8px}
.gap-3{gap:12px}
.gap-4{gap:16px}
.align-c{align-items:center}
.mt-1{margin-top:4px}
.mt-2{margin-top:8px}
.mt-3{margin-top:12px}
.mb-2{margin-bottom:8px}
.between{display:flex;align-items:center;justify-content:space-between;gap:10px}
.nowrap{white-space:nowrap}
.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kbd{display:inline-block;padding:1px 5px;font-size:10px;font-family:var(--mono);border:1px solid var(--rule-2);background:var(--bg-2);color:var(--muted);border-radius:0}
</style>
</head>
<body>

<!-- ─────────────────────  LOGIN OVERLAY  ───────────────────── -->
<div id="loginOverlay" class="login-overlay">
  <section class="login-box">
    <div class="login-brand">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>
      <span class="name">RUNTIME · OBSERVER</span>
    </div>
    <h1 class="login-title">Sign in</h1>
    <p class="login-hint">Use any username/password — admin is bootstrapped on first login.</p>
    <form id="loginForm" class="login-form">
      <input id="loginUsername" class="form-input" autocomplete="username" placeholder="username" required>
      <input id="loginPassword" class="form-input" type="password" autocomplete="current-password" placeholder="password" required>
      <button class="btn btn-primary" type="submit" style="justify-content:center;padding:9px">Sign in</button>
      <div id="loginError" class="login-err"></div>
    </form>
  </section>
</div>

<!-- ─────────────────────  SHELL  ───────────────────── -->
<div id="shell">

  <!-- TOP BAR -->
  <div class="topbar">
    <button class="brand" id="brand" title="Back to projects" type="button">
      <svg class="brand-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>
      <span class="brand-name">RUNTIME OBSERVER</span>
    </button>
    <div class="crumbs">
      <button class="crumb" id="crumbProject"><span class="key">PROJECT</span><span class="val" id="crumbProjectVal">—</span><span class="chev">▾</span></button>
      <button class="crumb" id="crumbApp"><span class="key">APP</span><span class="val" id="crumbAppVal">all</span><span class="chev">▾</span></button>
      <span class="crumb crumb-disabled" id="crumbPage"><span class="key">VIEW</span><span class="val" id="crumbPageVal">pulse</span></span>
    </div>
    <div class="top-actions">
      <span class="item"><span id="liveDot" class="live-dot pulsing"></span><span id="liveText">live · 10s</span></span>
      <button class="item" id="refreshBtn" title="Refresh now"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.5 15A9 9 0 1 1 20.4 6"/></svg>SYNC</button>
      <button class="item" id="themeBtn" title="Toggle theme"><svg id="iconSun" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/></svg><svg id="iconMoon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/></svg></button>
      <span class="item user-chip"><span id="userWho" class="who">—</span></span>
      <button class="item" id="logoutBtn">SIGN OUT</button>
      <span class="item"><span class="env-badge" id="envBadge">DEV</span></span>
    </div>
  </div>

  <!-- SUB BAR (context filters; visible only inside a project) -->
  <div class="subbar" id="subbar">
    <div class="sb-group">
      <button class="sb-pill" id="backToProjectsBtn" title="Back to projects">← PROJECTS</button>
    </div>
    <div class="sb-group">
      <span class="sb-label">WINDOW</span>
      <select class="sb-select" id="windowSelect">
        <option value="5">5m</option>
        <option value="15">15m</option>
        <option value="60" selected>1h</option>
        <option value="360">6h</option>
        <option value="1440">24h</option>
        <option value="0">all</option>
      </select>
    </div>
    <div class="sb-group">
      <span class="sb-label">REFRESH</span>
      <select class="sb-select" id="refreshSelect">
        <option value="1000">1s</option>
        <option value="10000" selected>10s</option>
        <option value="20000">20s</option>
        <option value="60000">60s</option>
        <option value="0">manual</option>
      </select>
    </div>
    <div class="sb-group" id="subbarSearchGroup" style="flex:1">
      <input class="sb-input" id="globalSearch" placeholder="search routes, paths, services...">
    </div>
    <div class="sb-group" style="border-right:0;margin-right:0">
      <button class="sb-pill" id="hiddenToggle" title="Show/hide hidden routes & deps">show hidden</button>
    </div>
  </div>

  <!-- LEFT RAIL -->
  <nav class="rail" id="rail">
    <button class="rail-btn" data-page="pulse" title="Pulse"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 12h4l3-9 4 18 3-9h4"/></svg><span class="tip">PULSE</span></button>
    <button class="rail-btn" data-page="traces" title="Traces"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 6h16M4 12h10M4 18h7"/><circle cx="20" cy="12" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg><span class="tip">TRACES</span></button>
    <button class="rail-btn" data-page="routes" title="Routes"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 5h18M3 12h18M3 19h18"/></svg><span class="tip">ROUTES</span></button>
    <button class="rail-btn" data-page="logs" title="Logs"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4h16v16H4z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg><span class="tip">LOGS</span></button>
    <button class="rail-btn" data-page="errors" title="Errors"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18.5v.5"/></svg><span class="badge hidden" id="railErrBadge">0</span><span class="tip">ERRORS</span></button>
    <button class="rail-btn" data-page="deps" title="Dependencies"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M7.5 7.5l4 9M16.5 7.5l-4 9"/></svg><span class="tip">DEPS</span></button>
    <div class="rail-spacer"></div>
    <button class="rail-btn" data-page="settings" title="Settings"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.7l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.7.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.7.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5h0a1.6 1.6 0 0 0 1.7-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.7v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg><span class="tip">SETTINGS</span></button>
    <button class="rail-btn" id="railToggle" title="Toggle sidebar"><svg id="railToggleIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M15 6l-6 6 6 6"/></svg><span class="tip">COLLAPSE</span></button>
  </nav>

  <!-- MAIN -->
  <div class="main" id="main">
    <!-- pages render here -->
  </div>

</div>

<!-- ─────────────────────  DRAWER  ───────────────────── -->
<div id="drawerOverlay" class="drawer-overlay"></div>
<div id="drawer" class="drawer">
  <div class="drawer-head">
    <div>
      <div id="drawerTitle" class="drawer-title">—</div>
      <div id="drawerSub" class="drawer-sub"></div>
    </div>
    <button id="drawerClose" class="icon-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
  </div>
  <div id="drawerBody" class="drawer-body"></div>
</div>

<script>
(function(){
"use strict";

/* ───────────────────────────  THEME  ─────────────────────────── */
var savedTheme = localStorage.getItem("ro:theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
function syncThemeIcon(){
  var dark = document.documentElement.dataset.theme === "dark";
  document.getElementById("iconSun").style.display = dark ? "block" : "none";
  document.getElementById("iconMoon").style.display = dark ? "none" : "block";
}
syncThemeIcon();
function toggleTheme(){
  var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("ro:theme", next);
  syncThemeIcon();
  render();
}

/* ───────────────────────────  STATE  ─────────────────────────── */
var S = {
  user: null,
  projects: [],
  apps: [],
  routes: [],
  deps: [],
  recentLogs: [],
  recentErrors: [],
  eventKinds: [],
  logLevels: [],
  totals: {},
  entries: [],          // entrypoints (full route list incl hidden)
  hiddenPrefs: [],
  errorClusters: [],
  errorTimeline: [],
  metricsSeries: [],
  routeState: null,     // {route, traces, logs} for selected route
  selectedProject: "",
  selectedApp: "all",
  selectedRouteId: null,
  selectedTraceId: null,
  selectedClusterId: null,
  selectedDepId: null,
  selectedLogId: null,
  page: "pulse",
  windowMinutes: Number(localStorage.getItem("ro:window") || 60),
  refreshMs: Number(localStorage.getItem("ro:refresh") || 10000),
  showHidden: false,
  searchQuery: "",
  refreshTimer: null,
  isRefreshing: false,
  loading: 0,
  waterfallTab: "all",  // all | spans | deps | logs | raw
  copyCache: new Map(),
  traceMap: null,       // current loaded trace map data
  depContext: null,     // current loaded dep context
  tracesRouteSearch: "",
  tracesRoutePage: 1,
  tracesCallSearch: "",
  tracesCallPage: 1,
  tracesPageSize: 25,
  tracesRoutesCollapsed: localStorage.getItem("ro:tracesRoutesCollapsed") === "1",
  tracesCallsCollapsed: localStorage.getItem("ro:tracesCallsCollapsed") === "1",
  railExpanded: localStorage.getItem("ro:railExpanded") === "1",
  routesSort: { col: "calls", dir: "desc" },
  routesMethodFilter: "",
  depsSort: { col: "calls", dir: "desc" },
  projectHomeView: "groups",
  selectedProjectGroup: "",
};

/* ───────────────────────────  HELPERS  ─────────────────────────── */
var $ = function(id){ return document.getElementById(id); };
function esc(v){ return String(v == null ? "" : v).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]; }); }
function num(n){ return Number(n || 0).toLocaleString(); }
function fmtMs(v){
  if (v == null) return "—";
  var n = Number(v); if (!Number.isFinite(n)) return "—";
  if (n < 1)     return n.toFixed(2) + "ms";
  if (n < 1000)  return Math.round(n) + "ms";
  if (n < 60000) return (n/1000).toFixed(n < 10000 ? 2 : 1) + "s";
  if (n < 3600000)  return (n/60000).toFixed(1) + "m";
  return (n/3600000).toFixed(1) + "h";
}
function fmtPct(n){ if (n == null || !Number.isFinite(n)) return "—"; if (n === 0) return "0%"; if (n < 0.01) return "<0.01%"; return n.toFixed(2) + "%"; }
function sortRows(rows, columns, state){
  var def = columns[state.col] || columns[Object.keys(columns)[0]];
  var sign = state.dir === "asc" ? 1 : -1;
  return rows.slice().sort(function(a,b){
    var av = def.get(a), bv = def.get(b);
    if (def.numeric) return ((Number(av)||0) - (Number(bv)||0)) * sign;
    return String(av || "").toLowerCase().localeCompare(String(bv || "").toLowerCase()) * sign;
  });
}
function sortHeader(label, key, cls, state, attr){
  var arrow = state.col !== key ? "·" : (state.dir === "asc" ? "▲" : "▼");
  return '<th class="sortable ' + (cls || "") + '" ' + attr + '="' + key + '">' + esc(label) + ' <span class="arr">' + arrow + '</span></th>';
}
function toggleSort(state, key){
  if (state.col === key) state.dir = state.dir === "asc" ? "desc" : "asc";
  else { state.col = key; state.dir = "desc"; }
}
function fmtTs(v){
  if (!v) return "—";
  var d = new Date(v);
  if (!Number.isFinite(d.getTime())) return String(v);
  return d.toLocaleString(undefined, {month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});
}
function fmtTime(v){
  if (!v) return "—";
  var d = new Date(v);
  if (!Number.isFinite(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, {hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});
}
function fmtRel(v){
  if (!v) return "—";
  var d = new Date(v).getTime();
  if (!Number.isFinite(d)) return "—";
  var s = Math.max(0, Math.round((Date.now() - d) / 1000));
  if (s < 5) return "now";
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.round(s/60) + "m ago";
  if (s < 86400) return Math.round(s/3600) + "h ago";
  return Math.round(s/86400) + "d ago";
}
function pretty(v){ try { return JSON.stringify(typeof v === "string" ? JSON.parse(v) : v, null, 2); } catch(e){ return String(v == null ? "" : v); } }
function clamp(n, lo, hi){ return Math.max(lo, Math.min(hi, n)); }
function setLoading(on){ S.loading = Math.max(0, S.loading + (on ? 1 : -1)); document.body.classList.toggle("loading", S.loading > 0); }
async function withLoading(fn){ setLoading(true); try { return await fn(); } finally { setLoading(false); } }

/* ───────────────────────────  API  ─────────────────────────── */
async function api(path, opts){
  opts = opts || {};
  var r = await fetch(path, Object.assign({cache:"no-store"}, opts, {headers: Object.assign({"Content-Type":"application/json"}, opts.headers || {})}));
  if (r.status === 401){ showLogin(); throw new Error("auth required"); }
  if (!r.ok){ throw new Error(await r.text()); }
  return r.json();
}

/* ───────────────────────────  AUTH  ─────────────────────────── */
function showLogin(){
  if (S.refreshTimer) clearInterval(S.refreshTimer);
  $("loginOverlay").style.display = "grid";
}
function hideLogin(user){
  $("loginOverlay").style.display = "none";
  S.user = user;
  $("userWho").textContent = user ? user.username : "—";
}
async function checkAuth(){
  try { var data = await api("/api/auth/me"); hideLogin(data.user); return true; }
  catch(e){ return false; }
}
async function loginSubmit(ev){
  ev.preventDefault();
  $("loginError").textContent = "";
  var r = await fetch("/api/auth/login", {method:"POST", headers:{"content-type":"application/json"}, body: JSON.stringify({username:$("loginUsername").value, password:$("loginPassword").value})});
  if (!r.ok){ $("loginError").textContent = "Sign in failed"; return; }
  var data = await r.json();
  hideLogin(data.user);
  setRefresh(S.refreshMs);
  await refresh();
}
async function logout(){ await fetch("/api/auth/logout", {method:"POST"}); showLogin(); }

/* ───────────────────────────  SCOPING  ─────────────────────────── */
function inScope(rows){
  if (!S.selectedProject) return rows;
  var apps = S.apps.filter(function(a){ return a.project_name === S.selectedProject; });
  var appIds = new Set(apps.map(function(a){ return a.id; }));
  var scoped = rows.filter(function(r){
    if (r.project_name) return r.project_name === S.selectedProject;
    if (r.app_id) return appIds.has(r.app_id);
    if (r.id && apps.some(function(a){ return a.id === r.id; })) return true;
    return false;
  });
  if (S.selectedApp === "all") return scoped;
  return scoped.filter(function(r){ return r.app_id === S.selectedApp || r.id === S.selectedApp; });
}
function scopedApps(){ return S.apps.filter(function(a){ return !S.selectedProject || a.project_name === S.selectedProject; }); }
function appName(a){ return a && (a.display_name || a.service_name) || "unknown"; }
function projectGroup(p){ return (p && p.group_name) || "ungrouped"; }

/* ───────────────────────────  TIME WINDOW  ─────────────────────────── */
function logWindowQuery(){ return "log_window_minutes=" + encodeURIComponent(S.windowMinutes) + "&log_limit=1000"; }
function logWindowStartParam(){ if (!S.windowMinutes) return ""; return new Date(Date.now() - S.windowMinutes * 60000).toISOString(); }
function fmtWindow(){
  if (!S.windowMinutes) return "all retained";
  if (S.windowMinutes < 60) return "last " + S.windowMinutes + "m";
  if (S.windowMinutes < 1440) return "last " + (S.windowMinutes/60) + "h";
  return "last " + (S.windowMinutes/1440) + "d";
}

/* ───────────────────────────  REFRESH  ─────────────────────────── */
function setRefresh(ms){
  S.refreshMs = Number(ms) || 0;
  localStorage.setItem("ro:refresh", String(S.refreshMs));
  if (S.refreshTimer) clearInterval(S.refreshTimer);
  S.refreshTimer = null;
  var dot = $("liveDot");
  dot.classList.remove("paused", "error");
  if (S.refreshMs === 0){
    dot.classList.add("paused");
    dot.classList.remove("pulsing");
    $("liveText").textContent = "manual";
  } else {
    dot.classList.add("pulsing");
    $("liveText").textContent = "live · " + (S.refreshMs/1000) + "s";
    S.refreshTimer = setInterval(refresh, S.refreshMs);
  }
}

async function refresh(){
  if (S.isRefreshing) return;
  S.isRefreshing = true;
  try {
    var scope = S.selectedProject ? "&project_name=" + encodeURIComponent(S.selectedProject) : "";
    var appScope = S.selectedApp && S.selectedApp !== "all" ? "&app_id=" + encodeURIComponent(S.selectedApp) : "";
    var results = await Promise.all([
      api("/api/overview?" + logWindowQuery()),
      api("/api/projects"),
      api("/api/entrypoints?include_hidden=true"),
      api("/api/preferences/hidden"),
      api("/api/errors/clusters?limit=200" + scope + appScope),
      api("/api/errors/timeline?window_minutes=1440&bucket_minutes=60" + scope + appScope),
      api("/api/metrics/timeseries?window_minutes=" + Math.max(60, S.windowMinutes || 1440) + "&bucket_minutes=" + bucketSize() + scope + appScope),
    ]);
    var ov = results[0];
    S.apps = ov.apps || [];
    S.routes = ov.routes || [];
    S.deps = ov.dependencies || [];
    S.recentLogs = ov.recent_logs || [];
    S.recentErrors = ov.recent_errors || [];
    S.eventKinds = ov.event_kinds || [];
    S.logLevels = ov.log_levels || [];
    S.totals = ov.totals || {};
    S.projects = results[1] || [];
    S.entries = results[2] || [];
    S.hiddenPrefs = results[3] || [];
    S.errorClusters = results[4] || [];
    S.errorTimeline = results[5] || [];
    S.metricsSeries = results[6] || [];
    if (S.selectedProject && !S.projects.some(function(p){ return p.project_name === S.selectedProject; })){
      S.selectedProject = "";
    }
    if (S.selectedRouteId) await loadRoute(S.selectedRouteId, false);
    $("liveDot").classList.remove("error");
    render();
  } catch(err){
    $("liveDot").classList.add("error");
    $("liveText").textContent = "refresh failed";
    console.error(err);
  } finally {
    S.isRefreshing = false;
  }
}

function bucketSize(){
  var w = S.windowMinutes || 1440;
  if (w <= 60) return 5;
  if (w <= 360) return 15;
  if (w <= 1440) return 60;
  return 180;
}

/* ───────────────────────────  PAGE NAV  ─────────────────────────── */
function goto(page){
  S.page = page;
  document.querySelectorAll(".rail-btn").forEach(function(b){ b.classList.toggle("active", b.dataset.page === page); });
  $("crumbPageVal").textContent = page;
  render();
}

function resetTracesPageState(){
  S.tracesRouteSearch = "";
  S.tracesRoutePage = 1;
  S.tracesCallSearch = "";
  S.tracesCallPage = 1;
}

/* ───────────────────────────  PROJECTS  ─────────────────────────── */
function selectProject(name){
  S.selectedProject = name;
  S.selectedApp = "all";
  S.selectedRouteId = null;
  S.selectedTraceId = null;
  S.routeState = null;
  resetTracesPageState();
  if (!S.page || S.page === "projects") S.page = "pulse";
  render();
  withLoading(refresh);
}
function backToProjects(){
  S.selectedProject = "";
  S.selectedApp = "all";
  S.selectedRouteId = null;
  S.selectedTraceId = null;
  S.routeState = null;
  S.projectHomeView = "groups";
  S.selectedProjectGroup = "";
  resetTracesPageState();
  render();
}
function deleteProject(name){
  openDrawer({
    title: "Delete project",
    sub: "This permanently deletes telemetry, apps, routes, logs, traces, dependencies, and SDK keys.",
    bodyHTML: '<form id="deleteProjectForm" class="login-form">' +
      '<div class="panel"><div class="panel-head"><span class="panel-title">PROJECT</span></div><div class="panel-body"><span class="mono">' + esc(name) + '</span></div></div>' +
      '<label class="sb-label" for="deleteProjectConfirm">TYPE PROJECT NAME TO CONFIRM</label>' +
      '<input id="deleteProjectConfirm" class="form-input" autocomplete="off" placeholder="' + esc(name) + '" required>' +
      '<div id="deleteProjectError" class="login-err"></div>' +
      '<div class="flex gap-2 mt-3"><button class="btn btn-danger" type="submit">DELETE PROJECT</button><button class="btn" type="button" id="cancelDeleteProject">CANCEL</button></div>' +
    '</form>',
  });
  $("deleteProjectConfirm").focus();
  $("cancelDeleteProject").onclick = closeDrawer;
  $("deleteProjectForm").onsubmit = async function(ev){
    ev.preventDefault();
    if ($("deleteProjectConfirm").value !== name){
      $("deleteProjectError").textContent = "Project name does not match.";
      return;
    }
    await api("/api/projects/" + encodeURIComponent(name), {method:"DELETE"});
    closeDrawer();
    if (S.selectedProject === name) backToProjects();
    await refresh();
  };
}
async function createProjectKey(name, groupName){
  var opts = {method:"POST"};
  if (groupName !== undefined) opts.body = JSON.stringify({group_name: groupName});
  var data = await api("/api/projects/" + encodeURIComponent(name) + "/api-keys", opts);
  openDrawer({
    title: "New SDK key · " + data.project_name,
    sub: "Copy this key now. It is shown only once and stored as a hash.",
    bodyHTML: '<div style="display:flex;gap:8px;margin-bottom:14px"><button class="btn btn-primary" id="copyNewKey">COPY KEY</button><button class="btn" id="manageKeysFromNew" data-project="' + esc(data.project_name) + '">MANAGE KEYS</button></div>' +
              '<div class="panel"><div class="panel-head"><span class="panel-title">PROJECT</span></div><div class="panel-body"><span class="mono">' + esc(data.project_name) + '</span>' + (data.group_name ? ' <span class="chip info">' + esc(data.group_name) + '</span>' : '') + '</div></div>' +
              '<div class="panel"><div class="panel-head"><span class="panel-title">API KEY</span></div><div class="panel-body"><pre style="margin:0">' + esc(data.api_key) + '</pre></div></div>',
  });
  $("copyNewKey").onclick = async function(){
    try { await navigator.clipboard.writeText(data.api_key); $("copyNewKey").textContent = "✓ COPIED"; }
    catch(e){ $("copyNewKey").textContent = "COPY FAILED"; }
  };
  var mk = $("manageKeysFromNew");
  if (mk) mk.onclick = function(){ withLoading(function(){ return showProjectKeys(data.project_name); }); };
  await refresh();
}
async function updateProjectGroup(name, currentGroup){
  var groupName = prompt("Project group (examples: development, production, work, personal). Leave blank for no group.", currentGroup || "");
  if (groupName === null) return;
  await api("/api/projects/" + encodeURIComponent(name) + "/settings", {method:"PUT", body: JSON.stringify({group_name: groupName})});
  await refresh();
}
function promptNewProject(){
  var lockedGroup = S.selectedProjectGroup || "";
  openDrawer({
    title: "New project",
    sub: lockedGroup ? "This project will be added to group · <b>" + esc(lockedGroup) + "</b>" : "Choose a group or leave it blank for ungrouped.",
    bodyHTML: '<form id="newProjectForm" class="login-form">' +
      '<label class="sb-label" for="newProjectName">PROJECT NAME</label>' +
      '<input id="newProjectName" class="form-input" autocomplete="off" placeholder="default" required>' +
      '<label class="sb-label" for="newProjectGroup">GROUP</label>' +
      '<input id="newProjectGroup" class="form-input" autocomplete="off" placeholder="optional" value="' + esc(lockedGroup) + '" ' + (lockedGroup ? 'readonly' : '') + '>' +
      '<div class="flex gap-2 mt-3"><button class="btn btn-primary" type="submit">CREATE PROJECT</button><button class="btn" type="button" id="cancelNewProject">CANCEL</button></div>' +
    '</form>',
  });
  var nameInput = $("newProjectName");
  nameInput.focus();
  $("cancelNewProject").onclick = closeDrawer;
  $("newProjectForm").onsubmit = function(ev){
    ev.preventDefault();
    var name = String($("newProjectName").value || "").trim();
    var groupName = lockedGroup || String($("newProjectGroup").value || "").trim();
    if (!name) return;
    closeDrawer();
    withLoading(function(){ return createProjectKey(name, groupName); });
  };
}
async function showProjectKeys(name){
  var keys = await api("/api/projects/" + encodeURIComponent(name) + "/api-keys");
  var rows = keys.length ? keys.map(function(k){
    return '<tr><td>' + esc(k.name) + '</td><td class="mono dim">' + esc(k.prefix) + '</td><td class="dim">' + esc(fmtTs(k.created_at)) + '</td><td class="dim">' + esc(fmtTs(k.last_used_at)) + '</td><td class="status-cell">' + (k.revoked_at ? '<span class="chip bad">REVOKED</span>' : '<span class="chip good">ACTIVE</span>') + '</td><td class="action-cell">' + (k.revoked_at ? '' : '<button class="btn btn-sm btn-danger" data-revoke="' + esc(k.id) + '" data-project="' + esc(name) + '">REVOKE</button>') + '</td></tr>';
  }).join("") : '<tr><td colspan="6" class="dim" style="text-align:center;padding:24px">No SDK keys yet.</td></tr>';
  openDrawer({
    title: "SDK keys · " + name,
    sub: "Stored keys are hashed. Full key is only shown when generated.",
    bodyHTML: '<div style="margin-bottom:12px"><button class="btn btn-primary" data-genkey="' + esc(name) + '">+ NEW SDK KEY</button></div>' +
              '<div class="panel tbl-wrap" style="margin-bottom:0"><table class="tbl"><thead><tr><th>name</th><th>prefix</th><th>created</th><th>last used</th><th>status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>',
  });
  document.querySelectorAll("[data-genkey]").forEach(function(b){ b.onclick = function(){ withLoading(function(){ return createProjectKey(b.dataset.genkey); }); }; });
  document.querySelectorAll("[data-revoke]").forEach(function(b){
    b.onclick = async function(){
      if (!confirm("Revoke this SDK key?")) return;
      await withLoading(async function(){
        await api("/api/projects/" + encodeURIComponent(b.dataset.project) + "/api-keys/" + encodeURIComponent(b.dataset.revoke), {method:"DELETE"});
        await showProjectKeys(b.dataset.project);
        await refresh();
      });
    };
  });
}

/* ───────────────────────────  HIDDEN PREFS  ─────────────────────────── */
async function setHidden(kind, id, appId, hidden){
  if (hidden){
    await api("/api/preferences/hidden", {method:"POST", body: JSON.stringify({target_kind:kind, target_id:id, app_id:appId})});
    if (kind === "route" && S.selectedRouteId === id){ S.selectedRouteId = null; S.selectedTraceId = null; S.routeState = null; }
  } else {
    await api("/api/preferences/hidden/" + encodeURIComponent(kind) + "/" + encodeURIComponent(id) + (appId ? "?app_id=" + encodeURIComponent(appId) : ""), {method:"DELETE"});
  }
  await refresh();
}

/* ───────────────────────────  ROUTES / TRACES  ─────────────────────────── */
async function selectRoute(routeId){
  S.selectedRouteId = routeId;
  S.selectedTraceId = null;
  goto("traces");
  await withLoading(function(){ return loadRoute(routeId, true); });
  render();
}
async function loadRoute(routeId, openFirst){
  S.routeState = await api("/api/routes/" + encodeURIComponent(routeId) + "/requests");
  if (openFirst && S.routeState.traces && S.routeState.traces.length){
    S.selectedTraceId = S.routeState.traces[0].id;
    await loadTrace(S.selectedTraceId);
  }
}
async function selectTrace(traceId){
  S.selectedTraceId = traceId;
  S.waterfallTab = "all";
  await withLoading(function(){ return loadTrace(traceId); });
  render();
}
async function loadTrace(traceId){
  S.traceMap = await api("/api/traces/" + encodeURIComponent(traceId) + "/map?slim=true");
}

/* ───────────────────────────  AGENT COPY  ─────────────────────────── */
function copyKey(kind, id){ return kind + ":" + id; }
function copyStatus(kind, id){ var s = S.copyCache.get(copyKey(kind, id)); return s ? s.status : "missing"; }
function copyLabel(kind, id, ready){
  var s = copyStatus(kind, id);
  if (s === "loading") return "PREPARING…";
  if (s === "error") return "RETRY";
  return ready || "COPY FOR AI";
}
async function prepareAndCopy(kind, id, path, label){
  var key = copyKey(kind, id);
  var existing = S.copyCache.get(key);
  if (!existing || existing.status === "error"){
    S.copyCache.set(key, {status:"loading"});
    try {
      var data = await api(path);
      S.copyCache.set(key, {status:"ready", text: data.text});
      try { await navigator.clipboard.writeText(data.text); flashStatus("✓ COPIED " + label); }
      catch(e){ flashStatus("CLIPBOARD BLOCKED — see drawer", true); openManualCopy(data.text); }
    } catch(err){
      S.copyCache.set(key, {status:"error"});
      flashStatus("COPY FAILED", true);
    }
  } else if (existing.status === "ready"){
    try { await navigator.clipboard.writeText(existing.text); flashStatus("✓ COPIED " + label); }
    catch(e){ flashStatus("CLIPBOARD BLOCKED — see drawer", true); openManualCopy(existing.text); }
  }
  render();
}
function flashStatus(msg, isErr){
  var el = $("flashStatus");
  if (!el){
    el = document.createElement("div");
    el.id = "flashStatus";
    el.style.cssText = "position:fixed;bottom:24px;right:24px;padding:9px 14px;border:1px solid var(--rule-2);background:var(--panel);color:var(--ink);font-size:11px;letter-spacing:.06em;text-transform:uppercase;z-index:80;font-weight:600";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.borderColor = isErr ? "var(--bad)" : "var(--signal)";
  el.style.color = isErr ? "var(--bad)" : "var(--signal)";
  el.style.opacity = "1";
  clearTimeout(el._t);
  el._t = setTimeout(function(){ el.style.opacity = "0"; el.style.transition = "opacity .4s"; }, 2500);
}
function openManualCopy(text){
  openDrawer({
    title: "Manual copy",
    sub: "Browser blocked automatic clipboard. Press Cmd/Ctrl+C with the text selected.",
    bodyHTML: '<textarea id="manualCopyText" style="width:100%;min-height:60vh;background:var(--bg-2);color:var(--ink);border:1px solid var(--rule-2);padding:12px;font-family:var(--mono);font-size:12px"></textarea>',
  });
  var a = $("manualCopyText");
  a.value = text;
  a.focus();
  a.select();
}

/* ───────────────────────────  DRAWER  ─────────────────────────── */
function openDrawer(opts){
  $("drawerTitle").textContent = opts.title || "";
  $("drawerSub").innerHTML = opts.sub || "";
  $("drawerBody").innerHTML = opts.bodyHTML || "";
  $("drawer").classList.add("open");
  $("drawerOverlay").classList.add("open");
}
function closeDrawer(){
  $("drawer").classList.remove("open");
  $("drawerOverlay").classList.remove("open");
}

/* ───────────────────────────  RENDER · MAIN  ─────────────────────────── */
function render(){
  syncCrumbs();
  syncWindowControls();
  syncRailBadges();
  var shell = document.getElementById("shell");
  if (!S.selectedProject){
    shell.classList.add("no-project");
    document.getElementById("subbar").style.display = "none";
    document.getElementById("rail").style.display = "none";
    renderProjects();
    return;
  }
  shell.classList.remove("no-project");
  document.getElementById("subbar").style.display = "flex";
  document.getElementById("rail").style.display = "flex";
  applyRailExpanded();
  var page = S.page || "pulse";
  if (page === "pulse")    renderPulse();
  else if (page === "traces")  renderTraces();
  else if (page === "routes")  renderRoutes();
  else if (page === "logs")    renderLogs();
  else if (page === "errors")  renderErrors();
  else if (page === "deps")    renderDeps();
  else if (page === "settings") renderSettings();
  else renderPulse();
}
function syncCrumbs(){
  var pv = $("crumbProjectVal"); if (pv) pv.textContent = S.selectedProject || "choose one";
  var av = $("crumbAppVal"); if (av) av.textContent = S.selectedApp === "all" ? "all" : (appName(S.apps.find(function(a){ return a.id === S.selectedApp; })) || "?");
  var ac = $("crumbApp"); if (ac) ac.classList.toggle("crumb-disabled", !S.selectedProject);
}
function syncWindowControls(){
  var w = $("windowSelect"); if (w) w.value = String(S.windowMinutes);
  var r = $("refreshSelect"); if (r) r.value = String(S.refreshMs);
  var sh = $("hiddenToggle"); if (sh) sh.classList.toggle("active", S.showHidden);
}
function syncRailBadges(){
  var errs = inScope(S.errorClusters || []).reduce(function(a, c){ return a + Number(c.count || 0); }, 0);
  var b = $("railErrBadge");
  if (errs > 0){ b.classList.remove("hidden"); b.textContent = errs > 99 ? "99+" : String(errs); }
  else b.classList.add("hidden");
}

/* ───────────────────────────  RENDER · PROJECTS HOME  ─────────────────────────── */
function projectCard(p){
  var group = projectGroup(p);
  return '<div class="proj-card" data-project="' + esc(p.project_name) + '">' +
    '<div class="proj-name"><span>' + esc(p.display_name || p.project_name) + '</span><span class="chip ' + (p.error_count > 0 ? "bad" : (p.request_count > 0 ? "good" : "dim")) + '">' + (p.error_count > 0 ? p.error_count + " err" : (p.request_count > 0 ? "live" : "idle")) + '</span></div>' +
    '<div style="margin-bottom:10px"><span class="chip info">' + esc(group) + '</span></div>' +
    '<div class="proj-stats">' +
      '<div class="ps"><span class="num">' + num(p.app_count) + '</span><span class="lbl">apps</span></div>' +
      '<div class="ps"><span class="num">' + num(p.request_count) + '</span><span class="lbl">requests</span></div>' +
      '<div class="ps"><span class="num">' + num(p.api_key_count) + '</span><span class="lbl">sdk keys</span></div>' +
    '</div>' +
    '<div class="proj-meta"><span>created · ' + esc(fmtTs(p.created_at)) + '</span><span>last seen · ' + esc(fmtRel(p.last_seen)) + '</span></div>' +
    '<div class="proj-actions" onclick="event.stopPropagation()">' +
      '<button class="btn btn-primary btn-sm" data-open="' + esc(p.project_name) + '">OPEN →</button>' +
      '<button class="btn btn-sm" data-genkey="' + esc(p.project_name) + '">+ SDK KEY</button>' +
      '<button class="btn btn-sm" data-keys="' + esc(p.project_name) + '">KEYS</button>' +
      '<button class="btn btn-sm" data-group="' + esc(p.project_name) + '" data-current-group="' + esc(p.group_name || "") + '">GROUP</button>' +
      '<button class="btn btn-sm btn-danger" data-delproj="' + esc(p.project_name) + '">DELETE</button>' +
    '</div>' +
  '</div>';
}
function projectGroups(){
  var groups = {};
  S.projects.forEach(function(p){
    var name = projectGroup(p);
    var g = groups[name] || {name:name, project_count:0, app_count:0, request_count:0, error_count:0, api_key_count:0, last_seen:""};
    g.project_count += 1;
    g.app_count += Number(p.app_count || 0);
    g.request_count += Number(p.request_count || 0);
    g.error_count += Number(p.error_count || 0);
    g.api_key_count += Number(p.api_key_count || 0);
    if (p.last_seen && (!g.last_seen || String(p.last_seen) > String(g.last_seen))) g.last_seen = p.last_seen;
    groups[name] = g;
  });
  return Object.keys(groups).map(function(k){ return groups[k]; }).sort(function(a,b){ return String(b.last_seen || b.name).localeCompare(String(a.last_seen || a.name)); });
}
function groupCard(g){
  return '<div class="proj-card" data-open-group="' + esc(g.name) + '">' +
    '<div class="proj-name"><span>' + esc(g.name) + '</span><span class="chip ' + (g.error_count > 0 ? "bad" : (g.request_count > 0 ? "good" : "dim")) + '">' + (g.error_count > 0 ? g.error_count + " err" : (g.request_count > 0 ? "live" : "idle")) + '</span></div>' +
    '<div class="proj-stats">' +
      '<div class="ps"><span class="num">' + num(g.project_count) + '</span><span class="lbl">projects</span></div>' +
      '<div class="ps"><span class="num">' + num(g.app_count) + '</span><span class="lbl">apps</span></div>' +
      '<div class="ps"><span class="num">' + num(g.request_count) + '</span><span class="lbl">requests</span></div>' +
    '</div>' +
    '<div class="proj-meta"><span>sdk keys · ' + num(g.api_key_count) + '</span><span>last seen · ' + esc(fmtRel(g.last_seen)) + '</span></div>' +
    '<div class="proj-actions"><button class="btn btn-primary btn-sm" data-open-group="' + esc(g.name) + '">SHOW PROJECTS →</button></div>' +
  '</div>';
}
function renderProjects(){
  var projects = S.selectedProjectGroup ? S.projects.filter(function(p){ return projectGroup(p) === S.selectedProjectGroup; }) : S.projects;
  var cards = S.projectHomeView === "groups" ? projectGroups().map(groupCard).join("") : projects.map(projectCard).join("");
  if (!S.projects.length){
    cards = '<div class="empty" style="grid-column:1/-1"><div class="ico">∅</div><p>No projects yet. Create an SDK key for your first project, configure the SDK with that key, then exercise your app.</p><button class="btn btn-primary" id="firstKey">+ CREATE FIRST PROJECT</button></div>';
  } else if (!cards) {
    cards = '<div class="empty" style="grid-column:1/-1"><div class="ico">∅</div><p>No projects in this group.</p><button class="btn" id="clearGroupFilter">SHOW ALL PROJECTS</button></div>';
  }
  var filterHTML = S.selectedProjectGroup && S.projectHomeView === "projects" ? '<div class="proj-filter"><button class="btn btn-sm" id="backToGroups">← GROUPS</button><span>group · ' + esc(S.selectedProjectGroup) + '</span><button class="btn btn-sm" id="clearGroupFilter">ALL PROJECTS</button></div>' : '<div></div>';
  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Projects</div><div class="page-sub">Choose a group or project to inspect telemetry</div></div>' +
        '<div class="page-actions"><button class="btn btn-primary" id="newProj">+ NEW PROJECT</button></div>' +
      '</div>' +
      '<div class="page-body"><div class="proj-toolbar">' + filterHTML + '<div class="proj-toggle" role="group" aria-label="Project home view"><button id="viewGroups" class="' + (S.projectHomeView === "groups" ? "active" : "") + '">Groups</button><button id="viewProjects" class="' + (S.projectHomeView === "projects" ? "active" : "") + '">Projects</button></div></div><div class="proj-grid">' + cards + '</div></div>' +
    '</div>';
  document.querySelectorAll(".proj-card[data-project]").forEach(function(c){ c.onclick = function(){ selectProject(c.dataset.project); }; });
  document.querySelectorAll("[data-open-group]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); S.selectedProjectGroup = b.dataset.openGroup; S.projectHomeView = "projects"; localStorage.setItem("ro:projectHomeView", "projects"); renderProjects(); }; });
  document.querySelectorAll("[data-open]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); selectProject(b.dataset.open); }; });
  document.querySelectorAll("[data-genkey]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); withLoading(function(){ return createProjectKey(b.dataset.genkey); }); }; });
  document.querySelectorAll("[data-keys]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); withLoading(function(){ return showProjectKeys(b.dataset.keys); }); }; });
  document.querySelectorAll("[data-group]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); withLoading(function(){ return updateProjectGroup(b.dataset.group, b.dataset.currentGroup); }); }; });
  document.querySelectorAll("[data-delproj]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); withLoading(function(){ return deleteProject(b.dataset.delproj); }); }; });
  var vg = $("viewGroups"); if (vg) vg.onclick = function(){ S.projectHomeView = "groups"; S.selectedProjectGroup = ""; localStorage.setItem("ro:projectHomeView", "groups"); renderProjects(); };
  var vp = $("viewProjects"); if (vp) vp.onclick = function(){ S.projectHomeView = "projects"; localStorage.setItem("ro:projectHomeView", "projects"); renderProjects(); };
  var bg = $("backToGroups"); if (bg) bg.onclick = function(){ S.projectHomeView = "groups"; S.selectedProjectGroup = ""; localStorage.setItem("ro:projectHomeView", "groups"); renderProjects(); };
  var cf = $("clearGroupFilter"); if (cf) cf.onclick = function(){ S.selectedProjectGroup = ""; renderProjects(); };
  var np = $("newProj"); if (np) np.onclick = promptNewProject;
  var fk = $("firstKey"); if (fk) fk.onclick = promptNewProject;
}

/* ───────────────────────────  RENDER · PULSE  ─────────────────────────── */
function renderPulse(){
  var routes = inScope(S.routes || []);
  var errors = inScope(S.errorClusters || []);
  var deps = inScope(S.deps || []);
  var apps = scopedApps();
  var totalReq = S.selectedApp === "all" ? Number(S.totals.request_count || 0) : routes.reduce(function(a,r){ return a + Number(r.call_count||0); }, 0);
  var totalErr = errors.reduce(function(a,c){ return a + Number(c.count||0); }, 0);
  var seriesReq = (S.metricsSeries || []).reduce(function(a,b){ return a + Number(b.requests||0); }, 0);
  var seriesErr = (S.metricsSeries || []).reduce(function(a,b){ return a + Number(b.request_errors||0); }, 0);
  var p95Vals = routes.filter(function(r){ return Number(r.p95_ms||0) > 0; }).map(function(r){ return Number(r.p95_ms); });
  var p95Max = p95Vals.length ? Math.round(Math.max.apply(null, p95Vals)) : 0;
  var p50Avg = routes.length ? Math.round(routes.reduce(function(a,r){ return a + Number(r.p50_ms||0); }, 0) / routes.length) : 0;
  var errRate = totalReq > 0 ? (totalErr / totalReq * 100) : 0;
  var slow = routes.slice().filter(function(r){ return r.call_count > 0; }).sort(function(a,b){ return Number(b.p95_ms||0) - Number(a.p95_ms||0); }).slice(0, 5);
  var loudest = topServicesByLogs(8);
  var attentionRows = buildAttention(routes, errors, loudest);

  var vitalsHTML =
    '<div class="vitals">' +
      vital("REQ", num(totalReq), fmtWindow(), seriesReq, "req") +
      vital("P50", fmtMs(p50Avg), "avg across routes", null) +
      vital("P95", fmtMs(p95Max), "worst route p95", null) +
      vital("ERR", fmtPct(errRate), num(totalErr) + " errors", seriesErr, "err", totalErr > 0 ? (errRate > 1 ? "alert" : "warn") : "") +
      vital("DEPS", num(deps.length), num(deps.reduce(function(a,d){ return a + Number(d.call_count||0); }, 0)) + " calls", null) +
      vital("APPS", num(apps.length), apps.map(function(a){ return appName(a); }).slice(0,3).join(" · ") || "—", null) +
    '</div>';

  var attentionHTML = attentionRows.length
    ? '<div class="stream">' + attentionRows.map(function(r){
        return '<div class="stream-row" data-attn=\'' + esc(JSON.stringify(r)) + '\'>' +
          '<span class="chip ' + r.chipClass + '">' + esc(r.chip) + '</span>' +
          '<span class="when">' + esc(r.when) + '</span>' +
          '<span class="what">' + r.what + '</span>' +
          '<span class="meta">' + esc(r.meta) + '</span>' +
        '</div>';
      }).join("") + '</div>'
    : '<div class="empty" style="margin:14px"><div class="ico">▰</div><p>All clear. No errors, slow routes, or hot loops in the current window.</p></div>';

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Pulse</div><div class="page-sub">' + esc(S.selectedProject) + (S.selectedApp !== "all" ? " · " + esc(appName(S.apps.find(function(a){ return a.id === S.selectedApp; })) || "") : "") + ' · ' + fmtWindow() + '</div></div>' +
      '</div>' +
      '<div class="page-body">' +
        vitalsHTML +
        '<div class="panel"><div class="panel-head"><span class="panel-title">▰ Activity timeline</span><span class="panel-meta">' + (S.metricsSeries || []).length + ' buckets · ' + bucketSize() + 'm</span></div><div class="panel-body" id="timelineBody"></div></div>' +
        '<div style="display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:14px">' +
          '<div class="panel" style="margin-bottom:0"><div class="panel-head"><span class="panel-title">▸ Attention</span><span class="panel-meta">' + attentionRows.length + ' items</span></div><div class="panel-body no-pad" id="attentionBody">' + attentionHTML + '</div></div>' +
          '<div class="panel" style="margin-bottom:0"><div class="panel-head"><span class="panel-title">▰ Slowest routes</span></div><div class="panel-body no-pad" id="slowestBody"></div></div>' +
        '</div>' +
      '</div>' +
    '</div>';

  drawTimeline($("timelineBody"));
  $("slowestBody").innerHTML = slow.length ? slow.map(function(r){
    return '<div class="stream-row" data-route="' + esc(r.id) + '" style="grid-template-columns:48px 1fr auto auto;gap:12px">' +
      '<span class="method method-' + (["GET","POST","PUT","PATCH","DELETE"].indexOf(r.method) >= 0 ? r.method : "OTHER") + '">' + esc(r.method) + '</span>' +
      '<span class="what truncate">' + esc(r.route_pattern) + '</span>' +
      '<span class="meta">' + fmtMs(Number(r.p95_ms||0)) + ' p95</span>' +
      '<span class="meta dim">' + num(r.call_count) + ' calls</span>' +
    '</div>';
  }).join("") : '<div class="empty" style="margin:14px"><p>No route latency data in this window.</p></div>';
  document.querySelectorAll("[data-route]").forEach(function(el){ el.onclick = function(){ withLoading(function(){ return selectRoute(el.dataset.route); }); }; });
  document.querySelectorAll("[data-attn]").forEach(function(el){
    el.onclick = function(){
      var a = JSON.parse(el.dataset.attn);
      if (a.kind === "error" && a.routeId) withLoading(function(){ return selectRoute(a.routeId); });
      else if (a.kind === "error" && a.traceId) withLoading(function(){ return openTraceQuick(a.traceId); });
      else if (a.kind === "slow" && a.routeId) withLoading(function(){ return selectRoute(a.routeId); });
      else if (a.kind === "noise"){ goto("logs"); }
    };
  });
}
function vital(label, value, sub, total, kindSpark, mod){
  var sparkHTML = "";
  if (kindSpark){
    var series = (S.metricsSeries || []).slice(-30).map(function(b){
      return kindSpark === "err" ? Number(b.request_errors||0) + Number(b.error_logs||0) + Number(b.exceptions||0) : Number(b.requests||0);
    });
    var max = Math.max(1, Math.max.apply(null, series.length ? series : [1]));
    sparkHTML = '<div class="v-spark ' + (kindSpark === "err" ? "err" : "") + '">' + series.map(function(v){ return '<span style="height:' + Math.max(2, Math.round(v / max * 18)) + 'px"></span>'; }).join("") + '</div>';
  }
  return '<div class="vital ' + (mod || "") + '">' +
    '<span class="v-label">' + esc(label) + '</span>' +
    '<span class="v-num">' + esc(value) + '</span>' +
    '<span class="v-sub">' + esc(sub) + '</span>' +
    sparkHTML +
  '</div>';
}
function topServicesByLogs(n){
  var m = {};
  inScope(S.recentLogs || []).forEach(function(l){ var k = l.service_name || "unknown"; m[k] = (m[k]||0) + 1; });
  return Object.keys(m).map(function(k){ return {service:k, count:m[k]}; }).sort(function(a,b){ return b.count - a.count; }).slice(0, n);
}
function buildAttention(routes, errors, loudest){
  var rows = [];
  errors.slice(0, 5).forEach(function(c){
    rows.push({
      kind:"error",
      chip:"ERROR",
      chipClass:"bad",
      when: fmtRel(c.last_seen),
      what: '<b>' + esc(c.type) + '</b> <span class="dim">·</span> ' + esc(String(c.normalized_message || "").slice(0, 80)),
      meta: (c.method ? c.method + " " + (c.route_pattern || "") + " · " : "") + c.count + "×",
      routeId: c.route_id || null,
      traceId: c.sample_trace_id || null,
    });
  });
  routes.slice().filter(function(r){ return r.call_count > 0 && Number(r.p95_ms||0) > 500; }).sort(function(a,b){ return Number(b.p95_ms||0) - Number(a.p95_ms||0); }).slice(0, 3).forEach(function(r){
    rows.push({
      kind:"slow",
      chip:"SLOW",
      chipClass:"warn",
      when: fmtRel(r.last_seen),
      what: '<span class="method method-' + (["GET","POST","PUT","PATCH","DELETE"].indexOf(r.method) >= 0 ? r.method : "OTHER") + '">' + esc(r.method) + '</span> ' + esc(r.route_pattern),
      meta: fmtMs(Number(r.p95_ms||0)) + " p95 · " + num(r.call_count) + " calls",
      routeId: r.id,
    });
  });
  if (loudest[0] && loudest[0].count > 1000){
    rows.push({
      kind:"noise",
      chip:"NOISE",
      chipClass:"info",
      when: fmtWindow(),
      what: '<b>' + esc(loudest[0].service) + '</b> is the loudest service',
      meta: num(loudest[0].count) + " logs",
    });
  }
  return rows;
}

/* ───────────────────────────  TIMELINE CHART  ─────────────────────────── */
function drawTimeline(container){
  var s = S.metricsSeries || [];
  if (!s.length){ container.innerHTML = '<div class="empty"><p>No metrics in this window.</p></div>'; return; }
  var W = container.clientWidth - 4 || 800;
  var H = 140;
  var pad = {l: 36, r: 12, t: 8, b: 22};
  var iw = W - pad.l - pad.r;
  var ih = H - pad.t - pad.b;
  var maxReq = Math.max(1, Math.max.apply(null, s.map(function(b){ return Number(b.requests||0); })));
  var maxErr = Math.max(1, Math.max.apply(null, s.map(function(b){ return Number(b.request_errors||0) + Number(b.error_logs||0) + Number(b.exceptions||0); })));
  var max = Math.max(maxReq, maxErr);
  function x(i){ return pad.l + (s.length === 1 ? iw/2 : (i / (s.length - 1)) * iw); }
  function y(v){ return pad.t + ih - (v / max) * ih; }
  function path(getVal){
    var pts = s.map(function(b, i){ return x(i) + "," + y(getVal(b)); });
    return "M" + pts.join(" L");
  }
  function area(getVal){
    var p = path(getVal);
    return p + " L" + x(s.length-1) + "," + y(0) + " L" + x(0) + "," + y(0) + " Z";
  }
  var grids = [0.25, 0.5, 0.75, 1].map(function(f){ var yy = pad.t + ih - f * ih; return '<line class="grid" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + yy + '" y2="' + yy + '"/>' + '<text class="axis-text" x="' + (pad.l - 6) + '" y="' + (yy + 3) + '" text-anchor="end">' + Math.round(f * max) + '</text>'; }).join("");
  var ticks = s.map(function(b, i){ if (i % Math.max(1, Math.floor(s.length/6)) !== 0) return ""; return '<text class="axis-text" x="' + x(i) + '" y="' + (H - 4) + '" text-anchor="middle">' + fmtTime(b.bucket) + '</text>'; }).join("");
  container.innerHTML =
    '<div class="timeline" style="padding:0;border:0"><svg class="timeline-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      grids +
      '<path class="area-req" d="' + area(function(b){ return Number(b.requests||0); }) + '"/>' +
      '<path class="line-req" d="' + path(function(b){ return Number(b.requests||0); }) + '"/>' +
      '<path class="area-err" d="' + area(function(b){ return Number(b.request_errors||0) + Number(b.error_logs||0) + Number(b.exceptions||0); }) + '"/>' +
      '<path class="line-err" d="' + path(function(b){ return Number(b.request_errors||0) + Number(b.error_logs||0) + Number(b.exceptions||0); }) + '"/>' +
      ticks +
    '</svg><div class="timeline-legend"><span><span class="sw" style="background:var(--signal)"></span>requests</span><span><span class="sw" style="background:var(--bad)"></span>errors</span></div></div>';
}

/* ───────────────────────────  RENDER · TRACES  ─────────────────────────── */
function tracesRoutesList(){
  var rows = inScope(S.entries || []).filter(function(r){
    if (Number(r.call_count||0) === 0 && !S.showHidden) return false;
    if (!S.showHidden && r.hidden) return false;
    return true;
  });
  var q = (S.tracesRouteSearch || "").toLowerCase();
  if (q){
    rows = rows.filter(function(r){
      return ((r.route_pattern || "") + " " + (r.method || "") + " " + (r.service_name || "")).toLowerCase().includes(q);
    });
  }
  rows.sort(function(a,b){ return Number(b.call_count||0) - Number(a.call_count||0); });
  return rows;
}
function tracesCallsList(){
  var traces = ((S.routeState && S.routeState.traces) || []).slice();
  var q = (S.tracesCallSearch || "").toLowerCase();
  if (q){
    traces = traces.filter(function(t){
      var status = String(t.status_code || "");
      return (status + " " + (t.method||"") + " " + (t.route_pattern||"") + " " + (t.service_name||"") + " " + (t.id||"")).toLowerCase().includes(q);
    });
  }
  return traces;
}
function paginateRows(rows, page, size){
  size = size || 25;
  var total = rows.length;
  var pages = Math.max(1, Math.ceil(total/size));
  page = Math.min(Math.max(1, page||1), pages);
  var start = (page-1)*size;
  return { items: rows.slice(start, start+size), page: page, pages: pages, total: total, start: start, size: size };
}
function tracesPagerHTML(p, kind){
  var label = p.total === 0 ? '0 of 0' : ((p.start+1) + '–' + Math.min(p.start+p.size, p.total) + ' of ' + p.total);
  return '<div class="t-side-pager">' +
    '<button class="t-pager-btn" data-pager="' + kind + '" data-dir="prev" ' + (p.page <= 1 ? 'disabled' : '') + '>‹</button>' +
    '<span class="t-pager-info">' + label + '</span>' +
    '<button class="t-pager-btn" data-pager="' + kind + '" data-dir="next" ' + (p.page >= p.pages ? 'disabled' : '') + '>›</button>' +
    '</div>';
}
function renderTraces(){
  var routes = tracesRoutesList();
  if (!S.selectedRouteId && routes.length){
    S.selectedRouteId = routes[0].id;
    withLoading(function(){ return loadRoute(S.selectedRouteId, true); }).then(render);
  }
  var routePager = paginateRows(routes, S.tracesRoutePage, S.tracesPageSize);
  var routeListHTML = routePager.items.length ? routePager.items.map(function(r){
    var isActive = r.id === S.selectedRouteId;
    var m = ["GET","POST","PUT","PATCH","DELETE"].indexOf(r.method) >= 0 ? r.method : "OTHER";
    return '<div class="t-side-row ' + (isActive ? "active" : "") + '" data-route="' + esc(r.id) + '">' +
      '<div class="t-side-row-line"><span class="method method-' + m + '">' + esc(r.method) + '</span><span class="truncate">' + esc(r.route_pattern) + '</span></div>' +
      '<div class="t-side-row-meta"><span class="truncate">' + esc(r.service_name || "—") + '</span><span>' + num(r.call_count) + '</span></div>' +
    '</div>';
  }).join("") : '<div class="empty" style="margin:14px"><p>' + (S.tracesRouteSearch ? "No routes match." : "No routes with traffic yet.") + '</p></div>';

  var calls = tracesCallsList();
  var callPager = paginateRows(calls, S.tracesCallPage, S.tracesPageSize);
  var callListHTML = callPager.items.length ? callPager.items.map(function(t){
    var ok = Number(t.status_code || 200) < 400;
    var isActive = t.id === S.selectedTraceId;
    var m = ["GET","POST","PUT","PATCH","DELETE"].indexOf(t.method || "GET") >= 0 ? (t.method || "GET") : "OTHER";
    return '<div class="trace-row ' + (isActive ? "active" : "") + '" data-trace="' + esc(t.id) + '">' +
      '<div class="status ' + (ok ? "ok" : "err") + '">' + esc(t.status_code || "—") + '</div>' +
      '<div>' +
        '<div class="route"><span class="method method-' + m + '">' + esc(t.method || "GET") + '</span>' + esc(t.route_pattern) + '</div>' +
        '<div class="meta">' + esc(t.service_name || "") + ' · ' + esc(fmtRel(t.finished_at || t.started_at)) + ' · ' + num(t.log_count || 0) + ' logs</div>' +
      '</div>' +
      '<div class="dur">' + fmtMs(Number(t.duration_ms || 0)) + '</div>' +
    '</div>';
  }).join("") : '<div class="empty" style="margin:14px"><div class="ico">∅</div>' + (function(){
    if (!S.selectedRouteId) return '<p>Pick a route on the left to see its calls.</p>';
    if (S.tracesCallSearch) return '<p>No calls match.</p>';
    var route = S.routeState && S.routeState.route;
    var hits = route && Number(route.call_count || 0);
    if (hits > 0){
      return '<p>This route has <b>' + num(hits) + '</b> aggregated call' + (hits === 1 ? '' : 's') + ' but no individual traces retained.</p>' +
        '<p class="hint">Per-trace detail is pruned after the trace retention window — only the aggregated counts/p95 survive. New calls will appear here.</p>';
    }
    return '<p>No traces captured for this route yet.</p>';
  })() + '</div>';

  var routesCollapsed = !!S.tracesRoutesCollapsed;
  var callsCollapsed = !!S.tracesCallsCollapsed;

  function routesColumnHTML(){
    if (routesCollapsed){
      return '<div class="t-collapsed-rail" data-collapse-toggle="routes" title="Expand routes">' +
        '<span class="t-collapsed-ico">»</span>' +
        '<span class="t-collapsed-label">Routes</span>' +
        '<span class="t-collapsed-count">' + num(routes.length) + '</span>' +
      '</div>';
    }
    return '<div class="t-side-head">' +
        '<input class="t-side-search" id="tracesRouteSearch" placeholder="search routes" value="' + esc(S.tracesRouteSearch || "") + '">' +
        '<button class="t-collapse-btn" data-collapse-toggle="routes" title="Collapse routes">‹</button>' +
      '</div>' +
      '<div class="t-side-list">' + routeListHTML + '</div>' +
      tracesPagerHTML(routePager, "routes");
  }
  function callsColumnHTML(){
    if (callsCollapsed){
      return '<div class="t-collapsed-rail" data-collapse-toggle="calls" title="Expand calls">' +
        '<span class="t-collapsed-ico">»</span>' +
        '<span class="t-collapsed-label">Calls</span>' +
        '<span class="t-collapsed-count">' + num(calls.length) + '</span>' +
      '</div>';
    }
    return '<div class="t-side-head">' +
        '<input class="t-side-search" id="tracesCallSearch" placeholder="search calls" value="' + esc(S.tracesCallSearch || "") + '"' + (S.selectedRouteId ? '' : ' disabled') + '>' +
        '<button class="t-collapse-btn" data-collapse-toggle="calls" title="Collapse calls">‹</button>' +
      '</div>' +
      '<div class="t-side-list" id="traceListCol">' + callListHTML + '</div>' +
      tracesPagerHTML(callPager, "calls");
  }

  var splitClasses = "split t-list-3col" + (routesCollapsed ? " r-collapsed" : "") + (callsCollapsed ? " c-collapsed" : "");

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Traces</div><div class="page-sub">' + (S.selectedRouteId && S.routeState && S.routeState.route ? esc(S.routeState.route.method + " " + S.routeState.route.route_pattern) : "select a route") + '</div></div>' +
      '</div>' +
      '<div class="' + splitClasses + '" style="flex:1;min-height:0">' +
        '<div class="col t-sidebar">' + routesColumnHTML() + '</div>' +
        '<div class="col t-sidebar">' + callsColumnHTML() + '</div>' +
        '<div class="col" id="waterfallCol"></div>' +
      '</div>' +
    '</div>';

  document.querySelectorAll("[data-route]").forEach(function(b){ b.onclick = function(){ S.tracesCallSearch = ""; S.tracesCallPage = 1; withLoading(function(){ return selectRoute(b.dataset.route); }); }; });
  document.querySelectorAll("[data-trace]").forEach(function(b){ b.onclick = function(){ withLoading(function(){ return selectTrace(b.dataset.trace); }); }; });
  document.querySelectorAll("[data-collapse-toggle]").forEach(function(b){
    b.onclick = function(ev){
      ev.stopPropagation();
      var which = b.dataset.collapseToggle;
      if (which === "routes"){
        S.tracesRoutesCollapsed = !S.tracesRoutesCollapsed;
        localStorage.setItem("ro:tracesRoutesCollapsed", S.tracesRoutesCollapsed ? "1" : "0");
      } else {
        S.tracesCallsCollapsed = !S.tracesCallsCollapsed;
        localStorage.setItem("ro:tracesCallsCollapsed", S.tracesCallsCollapsed ? "1" : "0");
      }
      renderTraces();
    };
  });

  var rs = $("tracesRouteSearch");
  if (rs){
    rs.oninput = function(){
      S.tracesRouteSearch = rs.value;
      S.tracesRoutePage = 1;
      renderTraces();
      var n = $("tracesRouteSearch");
      if (n){ n.focus(); n.setSelectionRange(n.value.length, n.value.length); }
    };
  }
  var cs = $("tracesCallSearch");
  if (cs){
    cs.oninput = function(){
      S.tracesCallSearch = cs.value;
      S.tracesCallPage = 1;
      renderTraces();
      var n = $("tracesCallSearch");
      if (n){ n.focus(); n.setSelectionRange(n.value.length, n.value.length); }
    };
  }
  document.querySelectorAll("[data-pager]").forEach(function(b){
    b.onclick = function(){
      var kind = b.dataset.pager;
      var step = b.dataset.dir === "next" ? 1 : -1;
      if (kind === "routes") S.tracesRoutePage = Math.max(1, (S.tracesRoutePage || 1) + step);
      else S.tracesCallPage = Math.max(1, (S.tracesCallPage || 1) + step);
      renderTraces();
    };
  });

  renderWaterfall();
}
function visibleEntries(){
  return inScope(S.entries || []).filter(function(r){
    if (Number(r.call_count||0) === 0 && !S.showHidden) return false;
    if (!S.showHidden && r.hidden) return false;
    if (!S.searchQuery) return true;
    return ((r.route_pattern || "") + " " + (r.method || "") + " " + (r.service_name || "")).toLowerCase().includes(S.searchQuery.toLowerCase());
  });
}
async function openTraceQuick(traceId){
  S.selectedTraceId = traceId;
  goto("traces");
  await loadTrace(traceId);
  // also try to load the route the trace belongs to
  if (S.traceMap && S.traceMap.traces && S.traceMap.traces[0]){
    var rid = S.traceMap.traces[0].route_id;
    if (rid && (!S.routeState || !S.routeState.route || S.routeState.route.id !== rid)){
      S.selectedRouteId = rid;
      await loadRoute(rid, false);
    }
  }
  render();
}

/* ─────────────  WATERFALL  ───────────── */
function renderWaterfall(){
  var col = $("waterfallCol");
  if (!col) return;
  if (!S.selectedTraceId || !S.traceMap){
    col.innerHTML = '<div class="empty" style="margin:14px"><div class="ico">▰</div><p>Pick a trace on the left to see its waterfall.</p></div>';
    return;
  }
  var d = S.traceMap;
  var rootTrace = (d.traces || [])[0] || {};
  var spans = collectSpans(d);
  var t0 = Math.min.apply(null, spans.map(function(s){ return s.t0; }));
  var t1 = Math.max.apply(null, spans.map(function(s){ return s.t1; }));
  if (!Number.isFinite(t0)) t0 = 0;
  if (!Number.isFinite(t1) || t1 <= t0) t1 = t0 + 1;
  var totalMs = t1 - t0;

  var ticks = [0, 0.25, 0.5, 0.75, 1].map(function(f){ return '<span style="left:' + (f*100) + '%">' + fmtMs(f * totalMs) + '</span>'; }).join("");

  S.wfExpanded = S.wfExpanded || {};
  var bars = spans.map(function(sp, idx){
    var leftPct = ((sp.t0 - t0) / totalMs) * 100;
    var widthPct = Math.max(0.4, ((sp.t1 - sp.t0) / totalMs) * 100);
    var rowKey = sp.kind + ":" + idx + ":" + sp.name.slice(0, 40);
    var open = !!S.wfExpanded[rowKey];
    var indent = sp.depth ? new Array(sp.depth + 1).join("· ") : "";
    var fullText = sp.tooltip || (sp.label + (sp.sublabel ? " — " + sp.sublabel : ""));
    var html = '<div class="wf-bar ' + (open ? "is-open" : "") + '" data-wfrow="' + esc(rowKey) + '" tabindex="0" title="' + esc(fullText) + '">' +
      '<div class="offset">' + (sp.t0 > 0.5 ? "+" + fmtMs(sp.t0) : "0") + '</div>' +
      '<div class="name"><span class="kind ' + sp.cssKind + '">' + esc(sp.kind) + '</span>' +
        (indent ? '<span class="indent">' + esc(indent) + '</span>' : '') +
        '<span class="label-col"><span class="label">' + esc(sp.label || sp.name) + '</span>' +
        (sp.sublabel ? '<span class="sublabel">' + esc(sp.sublabel) + '</span>' : '') +
        '</span></div>' +
      '<div class="track"><div class="fill ' + sp.cssKind + '" style="left:' + leftPct + '%;width:' + widthPct + '%"></div></div>' +
      '<div class="dur">' + fmtMs(sp.t1 - sp.t0) + '</div>' +
    '</div>';
    if (open) html += '<div class="wf-row-detail">' + renderSpanDetail(sp) + '</div>';
    return html;
  }).join("");

  var tabHTML = ["all","spans","deps","logs","raw"].map(function(t){
    return '<button class="wf-tab ' + (S.waterfallTab === t ? "active" : "") + '" role="tab" aria-selected="' + (S.waterfallTab === t ? "true" : "false") + '" data-wftab="' + t + '">' + t + '</button>';
  }).join("");

  var bodyHTML = "";
  if (S.waterfallTab === "all" || S.waterfallTab === "spans"){
    var axisHTML = '<div class="wf-axis" aria-hidden="true">' +
      '<span>+offset</span>' +
      '<span>span · operation</span>' +
      '<div class="ticks">' + ticks + '</div>' +
      '<span style="text-align:right">duration</span>' +
    '</div>';
    bodyHTML += axisHTML + '<div class="wf-bars">' + (bars || '<div class="empty"><p>No spans in this trace.</p></div>') + '</div>';
  }
  if (S.waterfallTab === "all" || S.waterfallTab === "deps"){
    bodyHTML += '<div style="margin-top:14px">' + renderDepDetails(d.dependencies || []) + '</div>';
  }
  if (S.waterfallTab === "all" || S.waterfallTab === "logs"){
    var flowLogs = d.flow_logs || d.logs || [];
    var bg = d.nearby_background_logs || [];
    bodyHTML += '<div class="panel" style="margin-top:14px"><div class="panel-head"><span class="panel-title">▸ Exact flow logs</span><span class="panel-meta">' + flowLogs.length + ' lines</span></div><div class="panel-body no-pad">' + renderLogStream(flowLogs) + '</div></div>';
    if (bg.length){
      bodyHTML += '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Nearby background logs</span><span class="panel-meta">' + bg.length + ' lines</span></div><div class="panel-body no-pad">' + renderLogStream(bg.slice(0, 80)) + '</div></div>';
    }
  }
  if (S.waterfallTab === "raw"){
    bodyHTML += '<pre>' + esc(pretty(d)) + '</pre>';
  }

  var ok = Number(rootTrace.status_code || 200) < 400;
  col.innerHTML =
    '<div class="waterfall">' +
      '<div class="wf-head">' +
        '<div class="wf-title"><span class="chip ' + (ok ? "good" : "bad") + '">' + esc(rootTrace.status_code || "—") + '</span><span>' + esc((rootTrace.method || "") + " " + (rootTrace.route_pattern || "")) + '</span></div>' +
        '<div class="wf-meta">' +
          '<span class="kv"><span class="k">trace</span><span class="v mono">' + esc(S.selectedTraceId.slice(0, 12)) + '…</span></span>' +
          '<span class="kv"><span class="k">duration</span><span class="v">' + fmtMs(Number(rootTrace.duration_ms || totalMs)) + '</span></span>' +
          '<span class="kv"><span class="k">spans</span><span class="v">' + (d.spans || []).length + '</span></span>' +
          '<span class="kv"><span class="k">deps</span><span class="v">' + (d.dependencies || []).length + '</span></span>' +
          '<span class="kv"><span class="k">errors</span><span class="v">' + (d.exceptions || []).length + '</span></span>' +
          '<span class="kv"><span class="k">started</span><span class="v">' + esc(fmtTs(rootTrace.started_at)) + '</span></span>' +
        '</div>' +
        '<div class="wf-actions">' +
          '<button class="btn btn-primary" id="copyTraceBtn">' + copyLabel("trace", S.selectedTraceId, "COPY TRACE FOR AI") + '</button>' +
          '<button class="btn" id="raw">VIEW RAW</button>' +
        '</div>' +
      '</div>' +
      '<div class="wf-tabs">' + tabHTML + '</div>' +
      bodyHTML +
    '</div>';

  $("copyTraceBtn").onclick = function(){ prepareAndCopy("trace", S.selectedTraceId, "/api/traces/" + encodeURIComponent(S.selectedTraceId) + "/agent-context", "TRACE"); };
  $("raw").onclick = function(){ S.waterfallTab = "raw"; renderWaterfall(); };
  document.querySelectorAll("[data-wftab]").forEach(function(b){ b.onclick = function(){ S.waterfallTab = b.dataset.wftab; renderWaterfall(); }; });
  document.querySelectorAll("#waterfallCol [data-wfrow]").forEach(function(b){
    function toggle(){
      var key = b.dataset.wfrow;
      S.wfExpanded[key] = !S.wfExpanded[key];
      renderWaterfall();
    }
    b.onclick = toggle;
    b.onkeydown = function(ev){ if (ev.key === "Enter" || ev.key === " "){ ev.preventDefault(); toggle(); } };
  });
  document.querySelectorAll("#waterfallCol [data-deprow]").forEach(function(b){
    b.onclick = function(ev){
      if (ev.target.closest("[data-copy-pre]")) return;
      var key = b.dataset.deprow;
      S.depExpanded = S.depExpanded || {};
      S.depExpanded[key] = !S.depExpanded[key];
      renderWaterfall();
    };
  });
  document.querySelectorAll("#waterfallCol [data-copy-pre]").forEach(function(b){
    b.onclick = function(ev){
      ev.stopPropagation();
      var pre = b.closest(".sql-block").querySelector(".sql-pre");
      if (!pre) return;
      try {
        navigator.clipboard.writeText(pre.textContent || "");
        var prev = b.textContent;
        b.textContent = "COPIED";
        setTimeout(function(){ b.textContent = prev; }, 900);
      } catch(e){ /* clipboard blocked */ }
    };
  });

  var allLogs = (d.flow_logs || d.logs || []).concat(d.nearby_background_logs || []);
  document.querySelectorAll("#waterfallCol [data-log]").forEach(function(el){
    el.onclick = function(){
      var meta = JSON.parse(el.dataset.log);
      if (meta.trace_id && meta.trace_id !== S.selectedTraceId){
        withLoading(function(){ return openTraceQuick(meta.trace_id); });
        return;
      }
      var full = allLogs.find(function(r){ return r.id === meta.id; }) || {};
      var tsEl = el.querySelector(".ts");
      openDrawer({title: "Log record", sub: tsEl ? tsEl.textContent : "", bodyHTML: '<pre>' + esc(pretty(full)) + '</pre>'});
    };
  });
}
function parsePayload(raw){
  try { return JSON.parse(raw || "{}"); } catch(e){ return {}; }
}
function depBarLabels(dep){
  var p = parsePayload(dep.payload_json);
  if (dep.kind === "db_query"){
    var verb = String(p.operation || p.statement_template || "").trim().split(/\s+/)[0].toUpperCase();
    var table = p.target || (Array.isArray(p.tables) && p.tables[0]) || p.database || "";
    var label = (verb && table) ? (verb + " " + table) : (verb || table || "db_query");
    var sub = String(p.rendered_statement || p.statement_template || p.operation || "").replace(/\s+/g, " ").trim();
    return {label: label, sublabel: sub, payload: p};
  }
  if (dep.kind === "http_client_call"){
    var method = p.method || "GET";
    var host = p.host || (p.url && p.url.split("/")[2]) || "";
    var path = p.path || (p.url && p.url.replace(/^https?:\/\/[^/]+/, "")) || "";
    return {label: method + " " + (host || path), sublabel: path && host ? path : "", payload: p};
  }
  if ((dep.kind || "").indexOf("llm") >= 0){
    return {label: (p.provider || "llm") + " · " + (p.model || ""), sublabel: p.operation || "", payload: p};
  }
  return {label: p.target || p.host || dep.kind || "dependency", sublabel: p.operation || "", payload: p};
}
function collectSpans(d){
  // Build a sorted list of span-like items with t0/t1 in ms relative to trace start.
  var spans = [];
  var allEvents = [].concat(d.spans || [], d.dependencies || [], d.exceptions || []);
  var t0base = null;
  allEvents.forEach(function(e){
    var start = e.started_at || e.timestamp;
    if (!start) return;
    var t = new Date(start).getTime();
    if (Number.isFinite(t) && (t0base == null || t < t0base)) t0base = t;
  });
  // include trace start so root bar aligns
  (d.traces || []).forEach(function(t){
    var ts = t.started_at && new Date(t.started_at).getTime();
    if (Number.isFinite(ts) && (t0base == null || ts < t0base)) t0base = ts;
  });
  if (t0base == null) t0base = Date.now();
  function add(kind, cssKind, label, sublabel, item, raw, depth){
    var start = new Date(item.started_at || item.timestamp || t0base).getTime();
    var dur = Number(item.duration_ms != null ? item.duration_ms : (item.payload && item.payload.duration_ms) || 0);
    var t0 = isFinite(start) ? start - t0base : 0;
    spans.push({kind: kind, cssKind: cssKind, label: label, sublabel: sublabel || "", name: label, t0: t0, t1: t0 + dur, raw: raw, depth: depth || 0, tooltip: label + (sublabel ? " — " + sublabel : "")});
  }
  // root trace
  (d.traces || []).forEach(function(t){
    add("ROUTE", "http", (t.method || "") + " " + (t.route_pattern || ""), t.service_name || "", {started_at: t.started_at, duration_ms: t.duration_ms}, t, 0);
  });
  // function spans (indented under root)
  (d.spans || []).filter(function(s){ return s.kind === "function"; }).forEach(function(s){
    var p = parsePayload(s.payload_json);
    add("FN", "span", s.name || p.name || "fn", p.module || "", s, s, 1);
  });
  // dependencies (indented as children)
  (d.dependencies || []).forEach(function(dep){
    var info = depBarLabels(dep);
    var k = dep.kind === "db_query" ? "db" : dep.kind === "http_client_call" ? "http" : (dep.kind || "").indexOf("llm") >= 0 ? "llm" : "span";
    add(k.toUpperCase(), k, info.label, info.sublabel, {started_at: dep.timestamp, duration_ms: info.payload.duration_ms || 0}, Object.assign({}, dep, {_payload: info.payload}), 1);
  });
  // exceptions: 0-duration markers, drawn as thin red lines via CSS
  (d.exceptions || []).forEach(function(e){
    add("ERR", "error", (e.type || "Error") + ": " + (e.normalized_message || "").slice(0, 80), e.fingerprint || "", {started_at: e.last_seen, duration_ms: 0}, e, 1);
  });
  spans.sort(function(a,b){
    if (a.t0 !== b.t0) return a.t0 - b.t0;
    return (b.t1 - b.t0) - (a.t1 - a.t0);
  });
  return spans;
}
function renderSpanDetail(sp){
  var raw = sp.raw || {};
  var p = raw._payload || parsePayload(raw.payload_json) || {};
  var lines = [];
  function row(k, v){ if (v == null || v === "") return; lines.push('<div class="kvline"><span class="k">' + esc(k) + '</span><span class="v">' + esc(String(v)) + '</span></div>'); }
  row("kind", sp.kind);
  var startedRaw = sp.raw && (sp.raw.started_at || sp.raw.timestamp);
  row("started", startedRaw ? fmtTs(startedRaw) : "—");
  row("offset", "+" + fmtMs(sp.t0));
  row("duration", fmtMs(sp.t1 - sp.t0));
  if (sp.cssKind === "db"){
    row("target", p.target);
    row("operation", p.operation);
    if (p.rendered_statement) lines.push('<div class="kvline"><span class="k">sql</span><span class="v"><pre>' + esc(p.rendered_statement) + '</pre></span></div>');
    else if (p.statement_template) lines.push('<div class="kvline"><span class="k">sql</span><span class="v"><pre>' + esc(p.statement_template) + '</pre></span></div>');
    if (Array.isArray(p.parameters) && p.parameters.length) row("params", JSON.stringify(p.parameters).slice(0, 400));
    row("rows", p.row_count);
  } else if (sp.cssKind === "http"){
    row("method", p.method);
    row("url", p.url || ((p.host || "") + (p.path || "")));
    row("status", p.status_code);
    row("request", p.request_body && JSON.stringify(p.request_body).slice(0, 400));
    row("response", p.response_body && JSON.stringify(p.response_body).slice(0, 400));
  } else if (sp.cssKind === "llm"){
    row("provider", p.provider);
    row("model", p.model);
    row("input tokens", p.input_tokens);
    row("output tokens", p.output_tokens);
  } else if (sp.cssKind === "error"){
    row("type", raw.type);
    row("message", raw.normalized_message);
    if (raw.sample_trace_id) row("sample trace", raw.sample_trace_id);
  } else {
    row("name", sp.label);
    row("module", p.module);
  }
  if (raw.error_message || p.error_message) row("error", raw.error_message || p.error_message);
  lines.push('<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--dim);font-size:10px;text-transform:uppercase;letter-spacing:.06em">▸ raw payload</summary><pre style="margin-top:6px">' + esc(pretty(p && Object.keys(p).length ? p : raw)) + '</pre></details>');
  return lines.join("");
}
function sqlVerb(p){
  var op = String(p.operation || p.statement_template || p.rendered_statement || "").trim();
  var first = op.split(/\s+/)[0].toUpperCase();
  if (["SELECT","INSERT","UPDATE","DELETE","BEGIN","COMMIT","ROLLBACK","SAVEPOINT","RELEASE"].indexOf(first) >= 0) return first;
  return "QUERY";
}
function formatSql(sql){
  if (!sql) return "";
  // Light-touch pretty printer: break on major keywords without over-engineering.
  var keywords = ["SELECT","FROM","WHERE","LEFT JOIN","RIGHT JOIN","INNER JOIN","JOIN","GROUP BY","ORDER BY","HAVING","LIMIT","OFFSET","UNION ALL","UNION","ON CONFLICT","RETURNING","VALUES","SET","INSERT INTO","UPDATE","DELETE FROM"];
  var out = String(sql).replace(/\s+/g, " ").trim();
  keywords.forEach(function(kw){
    var re = new RegExp("\\s+" + kw.replace(/ /g, "\\s+") + "\\b", "gi");
    out = out.replace(re, "\n" + kw + " ");
  });
  // indent continuation of long select lists / AND / OR
  out = out.replace(/,\s*(?=[^\n])/g, ",\n  ");
  out = out.replace(/\s+(AND|OR)\s+/gi, "\n  $1 ");
  return out;
}
function renderDepDetails(deps){
  if (!deps || !deps.length) return '<div class="empty"><p>No dependency calls in this trace.</p></div>';
  S.depExpanded = S.depExpanded || {};
  var rows = deps.map(function(d, idx){
    var info = depBarLabels(d);
    var p = info.payload;
    var kind = d.kind === "db_query" ? "db" : d.kind === "http_client_call" ? "http" : "span";
    var rowKey = (d.id || "") + ":" + idx;
    var open = !!S.depExpanded[rowKey];
    var html = '<tr class="row-clickable ' + (open ? "is-open" : "") + '" data-deprow="' + esc(rowKey) + '" title="' + esc(info.label) + '">' +
      '<td class="dep-chev"><span class="chev">' + (open ? "▾" : "▸") + '</span></td>' +
      '<td><span class="chip ' + (kind==="db" ? "good" : kind==="http" ? "info" : "dim") + '">' + esc(d.kind || "dep") + '</span></td>' +
      '<td class="truncate"><span class="mono">' + esc(info.label) + '</span></td>' +
      '<td class="num">' + (p.duration_ms ? fmtMs(p.duration_ms) : "—") + '</td>' +
    '</tr>';
    if (open){
      html += '<tr class="dep-detail-row"><td colspan="4" style="padding:0;background:var(--bg-2);max-width:none"><div class="wf-row-detail">' + renderDepRowDetail(d, p) + '</div></td></tr>';
    }
    return html;
  }).join("");
  return '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Dependency details</span><span class="panel-meta">click a row to see the full SQL</span></div><div class="panel-body no-pad"><table class="tbl tbl-dep"><thead><tr><th style="width:24px"></th><th>kind</th><th>target</th><th class="num">ms</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
}
function renderDepRowDetail(dep, p){
  var lines = [];
  function row(k, v){ if (v == null || v === "") return; lines.push('<div class="kvline"><span class="k">' + esc(k) + '</span><span class="v">' + esc(String(v)) + '</span></div>'); }
  row("kind", dep.kind);
  row("target", p.target || p.host || p.database || p.model || "");
  row("operation", p.operation || p.method || "");
  row("duration", p.duration_ms != null ? fmtMs(p.duration_ms) : "");
  row("status", p.status_code);
  row("rows", p.row_count);
  // Pretty-printed SQL gets its own block (full-width, scrollable, copy-friendly).
  var sql = p.rendered_statement || p.statement_template || "";
  if (sql){
    var sqlLabel = p.rendered_statement ? "sql" : "sql template";
    var sqlPretty = formatSql(sql);
    lines.push('<div class="sql-block"><div class="sql-head"><span class="sql-label">' + sqlLabel + '</span><button class="btn btn-sm" data-copy-pre>COPY</button></div><pre class="sql-pre">' + esc(sqlPretty) + '</pre></div>');
  }
  if (Array.isArray(p.parameters) && p.parameters.length){
    lines.push('<div class="sql-block"><div class="sql-head"><span class="sql-label">parameters</span><button class="btn btn-sm" data-copy-pre>COPY</button></div><pre class="sql-pre">' + esc(JSON.stringify(p.parameters, null, 2)) + '</pre></div>');
  }
  if (p.url) row("url", p.url);
  if (p.error_message) row("error", p.error_message);
  lines.push('<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--dim);font-size:10px;text-transform:uppercase;letter-spacing:.06em">▸ raw payload</summary><pre style="margin-top:6px">' + esc(pretty(p)) + '</pre></details>');
  return lines.join("");
}
function renderLogStream(logs){
  if (!logs || !logs.length) return '<div class="empty"><p>No logs.</p></div>';
  return logs.map(function(l){
    return '<div class="log-row" data-logid="' + esc(l.id || "") + '" data-log=\'' + esc(JSON.stringify({id:l.id, trace_id:l.trace_id})) + '\'>' +
      '<span class="ts">' + esc(fmtTs(l.timestamp)) + '</span>' +
      '<span class="lvl ' + esc(l.level || "INFO") + '">' + esc(l.level || "LOG") + '</span>' +
      '<span class="svc truncate">' + esc(l.service_name || "") + '</span>' +
      '<span class="msg">' + esc(l.message || "") + (l.logger_name ? '<div class="lname">' + esc(l.logger_name) + '</div>' : "") + '</span>' +
    '</div>';
  }).join("");
}

/* ───────────────────────────  RENDER · ROUTES  ─────────────────────────── */
var ROUTE_COLUMNS = {
  method:    { get: function(r){ return r.method || "GET"; }, numeric: false },
  route:     { get: function(r){ return r.route_pattern || ""; }, numeric: false },
  service:   { get: function(r){ return r.service_name || ""; }, numeric: false },
  calls:     { get: function(r){ return Number(r.call_count||0); }, numeric: true },
  errors:    { get: function(r){ return Number(r.error_count||0); }, numeric: true },
  p50:       { get: function(r){ return Number(r.p50_ms||0); }, numeric: true },
  p95:       { get: function(r){ return Number(r.p95_ms||0); }, numeric: true },
  last_seen: { get: function(r){ return r.last_seen || ""; }, numeric: false }
};

function renderRoutes(){
  var rows = visibleEntries();
  var method = S.routesMethodFilter || "";
  if (method) rows = rows.filter(function(r){
    var m = r.method || "GET";
    return method === "OTHER" ? ["GET","POST","PUT","PATCH","DELETE"].indexOf(m) < 0 : m === method;
  });

  var sorted = sortRows(rows, ROUTE_COLUMNS, S.routesSort);
  var totalEntries = (S.entries || []).length;
  var hidden = totalEntries - sorted.length;

  var methods = ["", "GET", "POST", "PUT", "PATCH", "DELETE", "OTHER"];
  var methodPills = methods.map(function(m){
    return '<button class="sb-pill ' + (S.routesMethodFilter === m ? "active" : "") + '" data-route-method="' + esc(m) + '">' + (m || "ALL") + '</button>';
  }).join("");
  var clearBtn = (method || S.searchQuery) ? '<button class="sb-pill" id="routesClear" title="Clear filters">CLEAR</button>' : "";

  var html = sorted.length ? '<table class="tbl"><thead><tr>' +
      sortHeader("method",    "method",    "",    S.routesSort, "data-sort-routes") +
      sortHeader("route",     "route",     "",    S.routesSort, "data-sort-routes") +
      sortHeader("service",   "service",   "",    S.routesSort, "data-sort-routes") +
      sortHeader("calls",     "calls",     "num", S.routesSort, "data-sort-routes") +
      sortHeader("errors",    "errors",    "num", S.routesSort, "data-sort-routes") +
      sortHeader("p50",       "p50",       "num", S.routesSort, "data-sort-routes") +
      sortHeader("p95",       "p95",       "num", S.routesSort, "data-sort-routes") +
      sortHeader("last seen", "last_seen", "",    S.routesSort, "data-sort-routes") +
      '<th class="num"></th>' +
    '</tr></thead><tbody>' + sorted.map(function(r){
      var m = r.method || "GET";
      var mcls = "method-" + (["GET","POST","PUT","PATCH","DELETE"].indexOf(m) >= 0 ? m : "OTHER");
      var errRate = r.call_count > 0 ? (Number(r.error_count||0) / Number(r.call_count) * 100) : 0;
      return '<tr class="row-clickable" data-route="' + esc(r.id) + '">' +
        '<td><span class="method ' + mcls + '">' + esc(m) + '</span></td>' +
        '<td class="truncate"><span class="mono">' + esc(r.route_pattern) + '</span>' + (r.hidden ? ' <span class="chip dim">HIDDEN</span>' : '') + '</td>' +
        '<td class="dim">' + esc(r.service_name || "") + '</td>' +
        '<td class="num">' + num(r.call_count) + '</td>' +
        '<td class="num ' + (errRate > 1 ? "txt-bad" : "") + '">' + num(r.error_count) + (errRate > 0 ? ' <span class="dim">(' + errRate.toFixed(1) + '%)</span>' : '') + '</td>' +
        '<td class="num">' + fmtMs(Number(r.p50_ms||0)) + '</td>' +
        '<td class="num">' + fmtMs(Number(r.p95_ms||0)) + '</td>' +
        '<td class="dim">' + esc(fmtRel(r.last_seen)) + '</td>' +
        '<td><button class="icon-btn" data-hide-route="' + esc(r.id) + '" data-app="' + esc(r.app_id) + '" data-hidden="' + (r.hidden ? "1" : "0") + '" title="' + (r.hidden ? "Restore" : "Hide") + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' + (r.hidden ? '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>' : '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13 13 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13 13 0 0 0 2 12s3 7 10 7a9.7 9.7 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>') + '</svg></button></td>' +
      '</tr>';
    }).join("") + '</tbody></table>'
    : '<div class="empty"><div class="ico">∅</div><p>No routes match your filters yet. Exercise the app and they will appear here.</p></div>';

  var subParts = [sorted.length + ' endpoint' + (sorted.length === 1 ? '' : 's')];
  if (hidden > 0) subParts.push(hidden + ' filtered');
  subParts.push('click any row to inspect traces');

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Routes</div><div class="page-sub">' + subParts.join(' · ') + '</div></div>' +
      '</div>' +
      '<div class="filter-row wrap" id="routesFilters">' + methodPills + clearBtn + '</div>' +
      '<div class="page-body" style="padding-top:0"><div class="panel" style="margin-bottom:0">' + html + '</div></div>' +
    '</div>';

  document.querySelectorAll("[data-route-method]").forEach(function(b){ b.onclick = function(){ S.routesMethodFilter = b.dataset.routeMethod; renderRoutes(); }; });
  if ($("routesClear")) $("routesClear").onclick = function(){ S.routesMethodFilter = ""; S.searchQuery = ""; var input = $("globalSearch"); if (input) input.value = ""; render(); };
  document.querySelectorAll("[data-sort-routes]").forEach(function(th){ th.onclick = function(){ toggleSort(S.routesSort, th.dataset.sortRoutes); renderRoutes(); }; });
  document.querySelectorAll("[data-route]").forEach(function(tr){ tr.onclick = function(ev){ if (ev.target.closest("[data-hide-route]")) return; withLoading(function(){ return selectRoute(tr.dataset.route); }); }; });
  document.querySelectorAll("[data-hide-route]").forEach(function(b){
    b.onclick = async function(ev){
      ev.preventDefault(); ev.stopPropagation();
      await withLoading(function(){ return setHidden("route", b.dataset.hideRoute, b.dataset.app || null, b.dataset.hidden !== "1"); });
    };
  });
}

/* ───────────────────────────  RENDER · LOGS  ─────────────────────────── */
function renderLogs(){
  var levels = ["", "ERROR", "WARNING", "INFO", "DEBUG"];
  var lvl = S.logLevel || "";
  var rows = inScope(S.recentLogs || []).filter(function(l){
    if (lvl && String(l.level || "").toUpperCase() !== lvl) return false;
    if (S.searchQuery){
      var q = S.searchQuery.toLowerCase();
      return (l.message || "").toLowerCase().includes(q) || (l.service_name || "").toLowerCase().includes(q);
    }
    return true;
  });
  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Logs</div><div class="page-sub">' + rows.length + ' · ' + fmtWindow() + '</div></div>' +
      '</div>' +
      '<div class="filter-row wrap" id="logFilters">' +
        levels.map(function(L){ return '<button class="sb-pill ' + (lvl === L ? "active" : "") + '" data-lvl="' + L + '">' + (L || "ALL") + '</button>'; }).join("") +
      '</div>' +
      '<div class="page-body" style="padding-top:0"><div class="panel" style="margin-bottom:0"><div class="panel-body no-pad" id="logStream">' + renderLogStream(rows.slice(0, 500)) + '</div></div></div>' +
    '</div>';
  document.querySelectorAll("[data-lvl]").forEach(function(b){ b.onclick = function(){ S.logLevel = b.dataset.lvl; renderLogs(); }; });
  document.querySelectorAll("[data-log]").forEach(function(el){
    el.onclick = function(){
      var meta = JSON.parse(el.dataset.log);
      if (meta.trace_id) withLoading(function(){ return openTraceQuick(meta.trace_id); });
      else openDrawer({title:"Log record", sub: el.querySelector(".ts").textContent, bodyHTML: '<pre>' + esc(pretty(rows.find(function(r){ return r.id === meta.id; }) || {})) + '</pre>'});
    };
  });
}

/* ───────────────────────────  RENDER · ERRORS  ─────────────────────────── */
function parseStackFrames(payload){
  if (!payload) return [];
  var stack = payload.stack || payload.frames || payload.traceback || [];
  if (typeof stack === "string"){
    return stack.split("\n").filter(Boolean).map(function(line){ return {raw: line}; });
  }
  if (!Array.isArray(stack)) return [];
  return stack.map(function(f){ return f || {}; });
}
function isUserFrame(frame){
  var file = String(frame.file || frame.filename || frame.path || "");
  if (!file) return false;
  if (/site-packages|dist-packages|\/runtime_observer\/|\/python3\.\d+\//.test(file)) return false;
  if (/\/starlette\/|\/fastapi\/|\/uvicorn\/|\/asyncio\/|\/sqlalchemy\//.test(file)) return false;
  return true;
}
function shortFile(file){
  if (!file) return "";
  if (file.length < 60) return file;
  var idx = file.indexOf("site-packages/");
  if (idx >= 0) return ".../" + file.slice(idx + "site-packages/".length);
  var parts = file.split("/");
  if (parts.length > 4) return ".../" + parts.slice(-3).join("/");
  return file;
}
function renderStackFrames(payload){
  var frames = parseStackFrames(payload);
  if (!frames.length) return '<div class="empty"><p>No stack frames captured.</p></div>';
  // Most languages emit frames innermost-last; show innermost (the throw site) at top.
  var ordered = frames.slice().reverse();
  return '<div class="stack-frames">' + ordered.map(function(f, idx){
    if (f.raw) return '<div class="stack-frame vendor"><span class="num">' + (idx + 1) + '</span><div class="body"><div class="fn">' + esc(f.raw) + '</div></div><span class="badge">raw</span></div>';
    var file = f.file || f.filename || f.path || "";
    var fn = f.function || f.func || f.name || "<anonymous>";
    var line = f.line != null ? f.line : (f.lineno != null ? f.lineno : "");
    var user = isUserFrame(f);
    var badge = user ? "app" : "vendor";
    return '<div class="stack-frame ' + (user ? "user" : "vendor") + '" title="' + esc(file) + (line ? ":" + line : "") + '">' +
      '<span class="num">' + (idx + 1) + '</span>' +
      '<div class="body">' +
        '<div class="fn">' + esc(fn) + '</div>' +
        '<div class="loc">' + esc(shortFile(file)) + (line ? ":" + esc(line) : "") + (f.module ? " · " + esc(f.module) : "") + '</div>' +
      '</div>' +
      '<span class="badge">' + badge + '</span>' +
    '</div>';
  }).join("") + '</div>';
}
function renderErrorTimelineContext(detail){
  // Build a unified before/at/after timeline from the sample trace + correlated logs.
  if (!detail || (!detail.trace && !detail.correlated_logs)) return '';
  var trace = detail.trace || {};
  var spans = (trace.spans || []).filter(function(s){ return s.kind === "function"; });
  var depKinds = {db_query: 1, http_client_call: 1, llm_call: 1};
  var deps = (trace.dependencies || (trace.events || []).filter(function(e){ return depKinds[e.kind]; }));
  var logs = detail.correlated_logs || (trace.logs || []);
  var exc = detail.exception || {};
  var ts = function(s){ return s ? new Date(s).getTime() : 0; };
  var errAt = ts(exc.last_seen || exc.first_seen);
  var items = [];
  spans.forEach(function(s){
    var p = parsePayload(s.payload_json);
    items.push({t: ts(s.started_at), kind: "FN", cssKind: "fn", desc: s.name || p.name || "fn", sub: p.module || "", dur: s.duration_ms, raw: s});
  });
  deps.forEach(function(dep){
    var info = depBarLabels(dep);
    var k = dep.kind === "db_query" ? "db" : dep.kind === "http_client_call" ? "http" : "span";
    items.push({t: ts(dep.timestamp), kind: k.toUpperCase(), cssKind: k, desc: info.label, sub: info.sublabel, dur: info.payload.duration_ms, raw: dep});
  });
  logs.forEach(function(l){
    var lvl = String(l.level || "INFO").toUpperCase();
    var cssK = lvl === "ERROR" || lvl === "CRITICAL" ? "error" : "log";
    items.push({t: ts(l.timestamp), kind: lvl, cssKind: cssK, desc: l.message || "", sub: l.logger_name || l.service_name || "", dur: null, raw: l});
  });
  if (errAt){
    items.push({t: errAt, kind: "ERROR", cssKind: "error", desc: (exc.type || "Error") + ": " + (exc.normalized_message || ""), sub: "", dur: null, isError: true, raw: exc});
  }
  if (!items.length) return '<div class="empty"><p>No surrounding spans, calls, or logs for this trace.</p></div>';
  items.sort(function(a,b){ return a.t - b.t; });
  var base = items[0].t;
  return '<div class="err-timeline">' + items.map(function(it){
    var rel = (it.t - base);
    var ts = (rel >= 0 ? "+" : "") + fmtMs(rel);
    var dur = it.dur != null ? fmtMs(it.dur) : "";
    return '<div class="err-timeline-row ' + (it.isError ? "is-error" : "") + '" title="' + esc(it.desc) + '">' +
      '<span class="ts">' + esc(ts) + '</span>' +
      '<span class="kind ' + it.cssKind + '">' + esc(it.kind) + '</span>' +
      '<span class="desc">' + esc(it.desc) + (it.sub ? ' <span class="dim">· ' + esc(it.sub) + '</span>' : '') + '</span>' +
      '<span class="dur">' + esc(dur) + '</span>' +
    '</div>';
  }).join("") + '</div>';
}
async function loadErrorDetail(cluster){
  if (!cluster || !cluster.app_id || !cluster.id) return null;
  S.errorDetailCache = S.errorDetailCache || {};
  var key = cluster.app_id + ":" + cluster.id;
  if (S.errorDetailCache[key]) return S.errorDetailCache[key];
  try {
    var detail = await api("/api/apps/" + encodeURIComponent(cluster.app_id) + "/exceptions/" + encodeURIComponent(cluster.id));
    S.errorDetailCache[key] = detail;
    return detail;
  } catch(e){ return null; }
}
function renderErrors(){
  var clusters = inScope(S.errorClusters || []);
  var selected = clusters.find(function(c){ return c.id === S.selectedClusterId; }) || clusters[0];
  if (selected && !S.selectedClusterId) S.selectedClusterId = selected.id;
  var clusterListHTML = clusters.length ? clusters.map(function(c){
    var isActive = c.id === S.selectedClusterId;
    return '<div class="trace-row ' + (isActive ? "active" : "") + '" data-cluster="' + esc(c.id) + '" data-app="' + esc(c.app_id) + '" style="grid-template-columns:1fr auto">' +
      '<div>' +
        '<div class="route"><span class="chip bad">' + esc(c.type) + '</span> <span class="truncate">' + esc(String(c.normalized_message || "").slice(0, 80)) + '</span></div>' +
        '<div class="meta">' + esc(c.service_name || "") + (c.route_pattern ? ' · ' + esc((c.method || "") + " " + c.route_pattern) : "") + ' · ' + esc(fmtRel(c.last_seen)) + '</div>' +
      '</div>' +
      '<div class="dur txt-bad">' + num(c.count) + '×</div>' +
    '</div>';
  }).join("") : '<div class="empty" style="margin:14px"><div class="ico">✓</div><p>No errors captured.</p></div>';

  var detailHTML = '<div class="empty" style="margin:14px"><div class="ico">✓</div><p>Pick a cluster to inspect.</p></div>';
  if (selected) detailHTML = '<div id="errDetailPane" class="waterfall">' + renderErrorDetailHeader(selected) + '<div class="dim" style="padding:14px">Loading error context…</div></div>';

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Errors</div><div class="page-sub">' + clusters.length + ' cluster' + (clusters.length === 1 ? '' : 's') + ' · ' + fmtWindow() + '</div></div>' +
      '</div>' +
      '<div class="page-body" style="padding-top:0">' +
        '<div class="panel" style="margin-bottom:14px"><div class="panel-head"><span class="panel-title">▰ Error timeline · 24h</span></div><div class="panel-body" id="errTimelineBody"></div></div>' +
        '<div class="split t-list" style="height:calc(100vh - 360px);border:1px solid var(--rule);border-top:1px solid var(--rule)">' +
          '<div class="col"><div class="error-cluster-list">' + clusterListHTML + '</div></div>' +
          '<div class="col">' + detailHTML + '</div>' +
        '</div>' +
      '</div>' +
    '</div>';
  drawErrTimeline($("errTimelineBody"));
  document.querySelectorAll("[data-cluster]").forEach(function(el){ el.onclick = function(){ S.selectedClusterId = el.dataset.cluster; renderErrors(); }; });
  document.querySelectorAll("[data-open-trace]").forEach(function(b){ b.onclick = function(){ withLoading(function(){ return openTraceQuick(b.dataset.openTrace); }); }; });

  if (selected){
    var loadingFor = selected.id;
    loadErrorDetail(selected).then(function(detail){
      if (S.selectedClusterId !== loadingFor) return;
      var pane = $("errDetailPane");
      if (!pane) return;
      pane.innerHTML = renderErrorDetailHeader(selected) + renderErrorDetailBody(selected, detail);
      pane.querySelectorAll("[data-open-trace]").forEach(function(b){ b.onclick = function(){ withLoading(function(){ return openTraceQuick(b.dataset.openTrace); }); }; });
    });
  }
}
function renderErrorDetailHeader(selected){
  return '<div class="wf-head">' +
    '<div class="wf-title"><span class="chip bad">' + esc(selected.type) + '</span><span class="truncate" title="' + esc(selected.normalized_message || "") + '">' + esc(String(selected.normalized_message || "").slice(0, 200)) + '</span></div>' +
    '<div class="wf-meta">' +
      '<span class="kv"><span class="k">service</span><span class="v">' + esc(selected.service_name || "—") + '</span></span>' +
      '<span class="kv"><span class="k">route</span><span class="v">' + esc((selected.method || "") + " " + (selected.route_pattern || "—")) + '</span></span>' +
      '<span class="kv"><span class="k">count</span><span class="v">' + num(selected.count) + '</span></span>' +
      '<span class="kv"><span class="k">first seen</span><span class="v">' + esc(fmtTs(selected.first_seen)) + '</span></span>' +
      '<span class="kv"><span class="k">last seen</span><span class="v">' + esc(fmtTs(selected.last_seen)) + '</span></span>' +
    '</div>' +
    '<div class="wf-actions">' +
      (selected.sample_trace_id ? '<button class="btn btn-primary" data-open-trace="' + esc(selected.sample_trace_id) + '">VIEW SAMPLE TRACE →</button>' : '<button class="btn" disabled>NO SAMPLE TRACE</button>') +
    '</div>' +
  '</div>';
}
function renderErrorDetailBody(selected, detail){
  var payload = parsePayload(selected.sample_payload_json);
  var msg = payload.message || selected.normalized_message || "";
  var stackPanel = '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Stack trace</span><span class="panel-meta">innermost first</span></div><div class="panel-body no-pad">' + renderStackFrames(payload) + '</div></div>';
  var msgPanel = msg ? '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Message</span></div><div class="panel-body"><div class="err-message error">' + esc(msg) + '</div></div></div>' : '';
  var timelinePanel = '';
  if (detail && (detail.trace || detail.correlated_logs)){
    timelinePanel = '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Calls &amp; logs around the error</span><span class="panel-meta">from sample trace</span></div><div class="panel-body no-pad">' + renderErrorTimelineContext(detail) + '</div></div>';
  } else if (detail === null){
    timelinePanel = '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Calls &amp; logs around the error</span></div><div class="panel-body"><div class="dim">No correlated trace context available.</div></div></div>';
  }
  var rawPanel = '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Raw payload</span></div><div class="panel-body no-pad"><pre style="margin:0;padding:14px;max-height:340px;overflow:auto">' + esc(pretty(payload)) + '</pre></div></div>';
  return '<div class="err-detail">' + msgPanel + stackPanel + timelinePanel + rawPanel + '</div>';
}
function drawErrTimeline(container){
  var s = S.errorTimeline || [];
  if (!s.length){ container.innerHTML = '<div class="dim" style="text-align:center;padding:20px">No error events in the last 24h.</div>'; return; }
  // bucket by hour, sum counts
  var byBucket = {};
  s.forEach(function(r){ byBucket[r.bucket] = (byBucket[r.bucket] || 0) + Number(r.count || 0); });
  var keys = Object.keys(byBucket).sort();
  var max = Math.max(1, Math.max.apply(null, keys.map(function(k){ return byBucket[k]; })));
  var W = container.clientWidth - 4 || 800;
  var H = 96;
  var pad = {l: 30, r: 8, t: 6, b: 18};
  var iw = W - pad.l - pad.r;
  var ih = H - pad.t - pad.b;
  var bw = iw / keys.length;
  var bars = keys.map(function(k, i){
    var v = byBucket[k];
    var h = (v / max) * ih;
    var x = pad.l + i * bw;
    var y = pad.t + ih - h;
    return '<rect x="' + (x + 1) + '" y="' + y + '" width="' + Math.max(2, bw - 2) + '" height="' + h + '" fill="var(--bad)" opacity="0.85"><title>' + esc(fmtTs(k)) + ' · ' + v + '</title></rect>';
  }).join("");
  var ticks = keys.map(function(k, i){ if (i % Math.max(1, Math.floor(keys.length/6)) !== 0) return ""; return '<text class="axis-text" x="' + (pad.l + i * bw + bw/2) + '" y="' + (H - 4) + '" text-anchor="middle">' + fmtTime(k) + '</text>'; }).join("");
  container.innerHTML = '<svg class="timeline-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
    '<text class="axis-text" x="' + (pad.l - 6) + '" y="' + (pad.t + 6) + '" text-anchor="end">' + max + '</text>' +
    '<text class="axis-text" x="' + (pad.l - 6) + '" y="' + (pad.t + ih + 2) + '" text-anchor="end">0</text>' +
    bars + ticks +
  '</svg>';
}

/* ───────────────────────────  RENDER · DEPS  ─────────────────────────── */
var DEP_COLUMNS = {
  target:    { get: function(d){ return d.target || ""; }, numeric: false },
  operation: { get: function(d){ return d.operation || ""; }, numeric: false },
  service:   { get: function(d){ return d.service_name || ""; }, numeric: false },
  calls:     { get: function(d){ return Number(d.call_count||0); }, numeric: true },
  errors:    { get: function(d){ return Number(d.error_count||0); }, numeric: true },
  p95:       { get: function(d){ return Number(d.p95_duration_ms||0); }, numeric: true }
};

function renderDeps(){
  var rows = inScope(S.deps || []).map(function(d){ return Object.assign({}, d, {label: depLabel(d)}); });
  var groupKey = function(d){
    if (d.dependency_type === "db") return "DB";
    if (d.dependency_type === "http") return "HTTP";
    if (d.dependency_type === "package") return "PACKAGE";
    return (d.dependency_type || "OTHER").toUpperCase();
  };
  var byGroup = {DB:[], HTTP:[], PACKAGE:[], OTHER:[]};
  rows.forEach(function(d){ var g = groupKey(d); (byGroup[g] || byGroup.OTHER).push(d); });
  var groups = ["DB", "HTTP", "PACKAGE", "OTHER"].filter(function(g){ return byGroup[g] && byGroup[g].length; });
  var active = S.selectedDepId || (rows[0] && rows[0].id);

  var groupTabs = groups.map(function(g){
    return '<button class="wf-tab ' + (S.depGroup === g ? "active" : "") + '" data-depg="' + g + '">' + g + ' · ' + byGroup[g].length + '</button>';
  }).join("");
  if (!S.depGroup || !byGroup[S.depGroup]) S.depGroup = groups[0] || "DB";
  var current = byGroup[S.depGroup] || [];

  var sortedDeps = sortRows(current, DEP_COLUMNS, S.depsSort);
  var html = sortedDeps.length ? '<table class="tbl"><thead><tr>' +
      sortHeader("target",    "target",    "",    S.depsSort, "data-sort-deps") +
      sortHeader("operation", "operation", "",    S.depsSort, "data-sort-deps") +
      sortHeader("service",   "service",   "",    S.depsSort, "data-sort-deps") +
      sortHeader("calls",     "calls",     "num", S.depsSort, "data-sort-deps") +
      sortHeader("errors",    "errors",    "num", S.depsSort, "data-sort-deps") +
      sortHeader("p95",       "p95",       "num", S.depsSort, "data-sort-deps") +
      '<th></th>' +
    '</tr></thead><tbody>' + sortedDeps.map(function(d){
      var errRate = d.call_count > 0 ? (Number(d.error_count||0) / Number(d.call_count) * 100) : 0;
      return '<tr class="row-clickable" data-dep="' + esc(d.id) + '">' +
        '<td class="truncate"><span class="mono">' + esc(d.target || "—") + '</span></td>' +
        '<td class="truncate dim">' + esc(d.operation || "") + '</td>' +
        '<td class="dim">' + esc(d.service_name || "") + '</td>' +
        '<td class="num">' + num(d.call_count) + '</td>' +
        '<td class="num ' + (errRate > 1 ? "txt-bad" : "") + '">' + num(d.error_count) + (errRate > 0 ? ' <span class="dim">(' + errRate.toFixed(1) + '%)</span>' : '') + '</td>' +
        '<td class="num">' + (d.p95_duration_ms ? fmtMs(Number(d.p95_duration_ms)) : "—") + '</td>' +
        '<td><button class="btn btn-sm" data-dep-copy="' + esc(d.id) + '">' + copyLabel("dep", d.id, "COPY") + '</button></td>' +
      '</tr>';
    }).join("") + '</tbody></table>' :
    '<div class="empty"><div class="ico">∅</div><p>No ' + S.depGroup + ' dependencies in this window.</p></div>';

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Dependencies</div><div class="page-sub">' + rows.length + ' dependency aggregate' + (rows.length === 1 ? '' : 's') + ' · ' + fmtWindow() + '</div></div>' +
      '</div>' +
      '<div class="filter-row wrap"><div class="wf-tabs" style="border-bottom:0">' + (groupTabs || '<span class="txt-dim">No dependencies.</span>') + '</div></div>' +
      '<div class="page-body" style="padding-top:0"><div class="panel" style="margin-bottom:0">' + html + '</div></div>' +
    '</div>';
  document.querySelectorAll("[data-depg]").forEach(function(b){ b.onclick = function(){ S.depGroup = b.dataset.depg; renderDeps(); }; });
  document.querySelectorAll("[data-sort-deps]").forEach(function(th){ th.onclick = function(){ toggleSort(S.depsSort, th.dataset.sortDeps); renderDeps(); }; });
  document.querySelectorAll("[data-dep]").forEach(function(tr){ tr.onclick = function(ev){ if (ev.target.closest("[data-dep-copy]")) return; var id = tr.dataset.dep; var d = rows.find(function(x){ return x.id === id; }); if (d) withLoading(function(){ return openDepDetail(d); }); }; });
  document.querySelectorAll("[data-dep-copy]").forEach(function(b){ b.onclick = function(ev){ ev.stopPropagation(); prepareAndCopy("dep", b.dataset.depCopy, "/api/dependencies/" + encodeURIComponent(b.dataset.depCopy) + "/agent-context", "DEP"); }; });
}
function depLabel(d){
  if (d.dependency_type === "db") return "DB · " + (d.target || "") + " · " + (d.operation || "");
  if (d.dependency_type === "http") return "HTTP " + (d.operation || "") + " " + (d.target || "");
  if (d.dependency_type === "package") return "pkg " + d.target;
  return (d.dependency_type || "dep") + " " + (d.target || "");
}
function depStatusChipClass(bucket){
  if (bucket === "2xx") return "good";
  if (bucket === "3xx") return "info";
  if (bucket === "4xx") return "warn";
  if (bucket === "5xx") return "bad";
  return "dim";
}
function depStatusCodeChipClass(code){
  var n = Number(code);
  if (!Number.isFinite(n) || n === 0) return "dim";
  if (n < 300) return "good";
  if (n < 400) return "info";
  if (n < 500) return "warn";
  return "bad";
}
function renderDepStats(d, stats){
  var errRate = d.call_count > 0 ? (Number(d.error_count||0) / Number(d.call_count) * 100) : 0;
  var tiles = [
    {label:"calls", value:num(d.call_count)},
    {label:"errors", value:num(d.error_count) + (errRate > 0 ? ' (' + errRate.toFixed(1) + '%)' : ''), cls: errRate > 1 ? "txt-bad" : ""},
    {label:"calls/min", value: stats && stats.calls_per_min ? Number(stats.calls_per_min).toFixed(2) : "—"},
    {label:"avg", value: stats ? fmtMs(stats.avg_ms) : "—"},
    {label:"p50", value: stats ? fmtMs(stats.p50_ms) : "—"},
    {label:"p95", value: stats ? fmtMs(stats.p95_ms) : fmtMs(d.p95_duration_ms)},
    {label:"max", value: stats ? fmtMs(stats.max_ms) : "—"}
  ];
  return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:8px;margin-bottom:14px">' +
    tiles.map(function(t){
      return '<div style="padding:8px 10px;border:1px solid var(--rule);background:var(--bg-2)">' +
        '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)">' + esc(t.label) + '</div>' +
        '<div class="mono ' + (t.cls || "") + '" style="font-size:14px;margin-top:2px">' + t.value + '</div>' +
      '</div>';
    }).join("") +
  '</div>';
}
function renderDepStatusDistribution(dist){
  if (!dist || !dist.length) return "";
  var total = dist.reduce(function(s, e){ return s + Number(e.count||0); }, 0);
  if (!total) return "";
  var bar = '<div style="display:flex;height:8px;border:1px solid var(--rule);background:var(--bg-2);overflow:hidden">' +
    dist.map(function(e){
      var pct = (Number(e.count) / total * 100).toFixed(2);
      var cls = depStatusChipClass(e.bucket);
      var color = cls === "good" ? "var(--good)" : cls === "info" ? "var(--info)" : cls === "warn" ? "var(--warn)" : cls === "bad" ? "var(--bad)" : "var(--dim)";
      return '<span title="' + esc(e.bucket + ": " + e.count) + '" style="width:' + pct + '%;background:' + color + '"></span>';
    }).join("") +
  '</div>';
  var legend = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">' +
    dist.map(function(e){
      var pct = (Number(e.count) / total * 100).toFixed(1);
      return '<span class="chip ' + depStatusChipClass(e.bucket) + '">' + esc(e.bucket) + ' · ' + num(e.count) + ' (' + pct + '%)</span>';
    }).join("") +
  '</div>';
  return '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Status code distribution</span><span class="panel-meta">' + num(total) + ' recent</span></div><div class="panel-body">' + bar + legend + '</div></div>';
}
function renderDepTopPaths(paths){
  if (!paths || !paths.length) return "";
  var rows = paths.map(function(p){
    var errPct = p.count > 0 ? (Number(p.error_count||0) / Number(p.count) * 100) : 0;
    return '<tr>' +
      '<td class="truncate"><span class="mono">' + esc(p.path || "/") + '</span></td>' +
      '<td class="num">' + num(p.count) + '</td>' +
      '<td class="num ' + (errPct > 1 ? "txt-bad" : "dim") + '">' + num(p.error_count || 0) + (errPct > 0 ? ' <span class="dim">(' + errPct.toFixed(1) + '%)</span>' : '') + '</td>' +
      '<td class="num">' + fmtMs(p.avg_ms) + '</td>' +
      '<td class="num">' + fmtMs(p.p95_ms) + '</td>' +
    '</tr>';
  }).join("");
  return '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Top paths</span><span class="panel-meta">' + paths.length + ' path' + (paths.length === 1 ? '' : 's') + '</span></div><div class="panel-body no-pad"><table class="tbl"><thead><tr><th>path</th><th class="num">calls</th><th class="num">errors</th><th class="num">avg</th><th class="num">p95</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
}
function renderDepRecentCalls(samples, isHttp){
  if (!samples || !samples.length) return '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Recent calls</span><span class="panel-meta">0</span></div><div class="panel-body"><div class="empty" style="border:0"><p>No recent calls retained.</p></div></div></div>';
  var rows = samples.map(function(s){
    var p = s.payload || {};
    var trace = s.trace_id ? ' <a data-open-trace="' + esc(s.trace_id) + '" style="color:var(--signal);text-decoration:underline;cursor:pointer">trace →</a>' : '';
    if (isHttp){
      var statusCell = p.status_code != null ? '<span class="chip ' + depStatusCodeChipClass(p.status_code) + '">' + esc(String(p.status_code)) + '</span>' : (p.error_type ? '<span class="chip bad">' + esc(p.error_type) + '</span>' : '<span class="chip dim">—</span>');
      return '<tr><td class="dim">' + esc(fmtTs(s.timestamp)) + '</td>' +
        '<td>' + statusCell + '</td>' +
        '<td class="truncate"><span class="mono">' + esc((p.method || "") + " " + (p.path || "/")) + '</span>' + trace + '</td>' +
        '<td class="num">' + fmtMs(p.duration_ms) + '</td></tr>';
    }
    var op = p.operation || p.statement_fingerprint || p.model || s.kind || "";
    return '<tr><td class="dim">' + esc(fmtTs(s.timestamp)) + '</td>' +
      '<td class="truncate"><span class="mono">' + esc(String(op).slice(0, 240)) + '</span>' + trace + '</td>' +
      '<td class="num">' + fmtMs(p.duration_ms) + '</td></tr>';
  }).join("");
  var header = isHttp
    ? '<thead><tr><th>time</th><th>status</th><th>method · path</th><th class="num">duration</th></tr></thead>'
    : '<thead><tr><th>time</th><th>operation</th><th class="num">duration</th></tr></thead>';
  return '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Recent calls</span><span class="panel-meta">' + samples.length + '</span></div><div class="panel-body no-pad"><table class="tbl">' + header + '<tbody>' + rows + '</tbody></table></div></div>';
}
async function openDepDetail(d){
  var ctx = await api("/api/dependencies/" + encodeURIComponent(d.id) + "/context");
  var isHttp = d.dependency_type === "http";
  var errs = (ctx.error_samples || []).map(function(e){
    return '<div class="log-row"><span class="ts">' + esc(fmtTs(e.timestamp)) + '</span><span class="lvl ERROR">ERR</span><span class="svc">' + esc((e.payload && e.payload.error_type) || "error") + '</span><span class="msg">' + esc((e.payload && e.payload.error_message) || "") + (e.trace_id ? ' <a data-open-trace="' + esc(e.trace_id) + '" style="color:var(--signal);text-decoration:underline;margin-left:6px">view trace →</a>' : '') + '</span></div>';
  }).join("");
  var related = (ctx.related_logs || []).map(function(l){
    return '<div class="log-row"><span class="ts">' + esc(fmtTs(l.timestamp)) + '</span><span class="lvl ' + esc(l.level || "INFO") + '">' + esc(l.level || "LOG") + '</span><span class="svc">' + esc(l.service_name || "") + '</span><span class="msg">' + esc(l.message || "") + '</span></div>';
  }).join("");
  openDrawer({
    title: "Dependency · " + (d.target || ""),
    sub: (d.service_name || "—") + " · " + num(d.call_count) + " calls · " + num(d.error_count) + " errors",
    bodyHTML:
      '<div style="display:flex;gap:8px;margin-bottom:14px"><button class="btn btn-primary" id="copyDepBtn">' + copyLabel("dep", d.id, "COPY FOR AI") + '</button></div>' +
      renderDepStats(d, ctx.stats) +
      (isHttp ? renderDepStatusDistribution(ctx.status_distribution) : "") +
      (isHttp ? renderDepTopPaths(ctx.top_paths) : "") +
      renderDepRecentCalls(ctx.samples, isHttp) +
      '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Error samples</span><span class="panel-meta">' + (ctx.error_samples || []).length + '</span></div><div class="panel-body no-pad">' + (errs || '<div class="empty" style="border:0"><p>No individual error payloads retained.</p></div>') + '</div></div>' +
      '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Related logs</span><span class="panel-meta">' + (ctx.related_logs || []).length + '</span></div><div class="panel-body no-pad">' + (related || '<div class="empty" style="border:0"><p>No related logs.</p></div>') + '</div></div>'
  });
  $("copyDepBtn").onclick = function(){ prepareAndCopy("dep", d.id, "/api/dependencies/" + encodeURIComponent(d.id) + "/agent-context", "DEP"); };
  document.querySelectorAll("[data-open-trace]").forEach(function(a){ a.style.cursor = "pointer"; a.onclick = function(ev){ ev.preventDefault(); closeDrawer(); withLoading(function(){ return openTraceQuick(a.dataset.openTrace); }); }; });
}

/* ───────────────────────────  RENDER · SETTINGS  ─────────────────────────── */
function renderSettings(){
  var hiddenRows = (S.hiddenPrefs || []).map(function(h){
    return '<tr><td>' + esc(h.target_kind) + '</td><td class="truncate mono dim">' + esc(h.target_id) + '</td><td class="dim">' + esc(h.app_id || "*") + '</td><td><button class="btn btn-sm" data-restore-kind="' + esc(h.target_kind) + '" data-restore-id="' + esc(h.target_id) + '" data-restore-app="' + esc(h.app_id || "") + '">RESTORE</button></td></tr>';
  }).join("") || '<tr><td colspan="4" class="dim" style="text-align:center;padding:24px">No hidden items.</td></tr>';

  $("main").innerHTML =
    '<div class="page">' +
      '<div class="page-header">' +
        '<div><div class="page-title">Settings</div><div class="page-sub">Project keys, hidden items, account</div></div>' +
      '</div>' +
      '<div class="page-body">' +
        '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Current project</span></div><div class="panel-body" style="display:flex;gap:8px;flex-wrap:wrap">' +
          '<button class="btn btn-primary" id="newKeyHere">+ NEW SDK KEY</button>' +
          '<button class="btn" id="manageKeysHere">MANAGE SDK KEYS</button>' +
          '<button class="btn btn-danger" id="deleteProjectHere">DELETE PROJECT</button>' +
          '<button class="btn" id="backToProjectsHere">← BACK TO PROJECTS</button>' +
        '</div></div>' +
        '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Hidden items</span><span class="panel-meta">' + (S.hiddenPrefs || []).length + '</span></div><div class="panel-body no-pad"><table class="tbl"><thead><tr><th>kind</th><th>id</th><th>app</th><th></th></tr></thead><tbody>' + hiddenRows + '</tbody></table></div></div>' +
        '<div class="panel"><div class="panel-head"><span class="panel-title">▸ Account</span></div><div class="panel-body">Signed in as <b>' + esc(S.user ? S.user.username : "—") + '</b> · <button class="btn btn-sm" id="logoutHere">SIGN OUT</button></div></div>' +
      '</div>' +
    '</div>';
  $("newKeyHere").onclick = function(){ withLoading(function(){ return createProjectKey(S.selectedProject); }); };
  $("manageKeysHere").onclick = function(){ withLoading(function(){ return showProjectKeys(S.selectedProject); }); };
  $("deleteProjectHere").onclick = function(){ withLoading(function(){ return deleteProject(S.selectedProject); }); };
  $("backToProjectsHere").onclick = function(){ backToProjects(); };
  $("logoutHere").onclick = logout;
  document.querySelectorAll("[data-restore-kind]").forEach(function(b){
    b.onclick = function(){ withLoading(function(){ return setHidden(b.dataset.restoreKind, b.dataset.restoreId, b.dataset.restoreApp || null, false); }); };
  });
}

/* ───────────────────────────  CRUMB MENUS  ─────────────────────────── */
function openProjectMenu(){
  if (!S.projects.length) return;
  var items = ['<button data-pick="" class="menu-item">↶ ALL PROJECTS</button>']
    .concat(S.projects.map(function(p){ return '<button data-pick="' + esc(p.project_name) + '" class="menu-item ' + (p.project_name === S.selectedProject ? "active" : "") + '">' + esc(p.project_name) + ' <span class="dim">· ' + num(p.request_count) + '</span></button>'; }))
    .join("");
  openMenu($("crumbProject"), items);
}
function openAppMenu(){
  if (!S.selectedProject) return;
  var apps = scopedApps();
  var items = ['<button data-app="all" class="menu-item ' + (S.selectedApp === "all" ? "active" : "") + '">ALL APPS</button>']
    .concat(apps.map(function(a){ return '<button data-app="' + esc(a.id) + '" class="menu-item ' + (S.selectedApp === a.id ? "active" : "") + '">' + esc(appName(a)) + ' <span class="dim">· ' + esc(a.language || "") + '</span></button>'; }))
    .join("");
  openMenu($("crumbApp"), items);
}
function openMenu(anchor, itemsHTML){
  closeMenus();
  var rect = anchor.getBoundingClientRect();
  var m = document.createElement("div");
  m.className = "popmenu";
  m.style.cssText = "position:fixed;top:" + (rect.bottom) + "px;left:" + rect.left + "px;min-width:" + Math.max(180, rect.width) + "px;background:var(--panel);border:1px solid var(--rule-2);z-index:60;max-height:60vh;overflow-y:auto;box-shadow:0 6px 24px rgba(0,0,0,.3)";
  m.innerHTML = '<style>.popmenu .menu-item{display:block;width:100%;text-align:left;padding:8px 12px;font-size:12px;color:var(--ink);border-bottom:1px solid var(--rule);transition:background .08s;text-transform:uppercase;letter-spacing:.04em;font-weight:500}.popmenu .menu-item:hover{background:var(--bg-2)}.popmenu .menu-item.active{color:var(--signal);background:var(--signal-soft)}.popmenu .menu-item:last-child{border-bottom:0}</style>' + itemsHTML;
  document.body.appendChild(m);
  m.querySelectorAll("[data-pick]").forEach(function(b){ b.onclick = function(){ closeMenus(); var v = b.dataset.pick; if (v) selectProject(v); else backToProjects(); }; });
  m.querySelectorAll("[data-app]").forEach(function(b){ b.onclick = function(){ closeMenus(); S.selectedApp = b.dataset.app; S.selectedRouteId = null; S.selectedTraceId = null; S.routeState = null; resetTracesPageState(); render(); withLoading(refresh); }; });
  setTimeout(function(){ document.addEventListener("click", _closeMenuHandler); }, 10);
}
function _closeMenuHandler(ev){ if (!ev.target.closest(".popmenu")) closeMenus(); }
function closeMenus(){ document.querySelectorAll(".popmenu").forEach(function(m){ m.remove(); }); document.removeEventListener("click", _closeMenuHandler); }

/* ───────────────────────────  RAIL EXPAND/COLLAPSE  ─────────────────────────── */
function applyRailExpanded(){
  var shell = document.getElementById("shell");
  var rail = document.getElementById("rail");
  var toggle = document.getElementById("railToggle");
  var icon = document.getElementById("railToggleIcon");
  var expanded = !!S.railExpanded;
  shell.classList.toggle("rail-expanded", expanded);
  rail.classList.toggle("expanded", expanded);
  if (icon){
    // chevron points left when expanded (click to collapse), right when collapsed (click to expand)
    icon.innerHTML = expanded ? '<path d="M15 6l-6 6 6 6"/>' : '<path d="M9 6l6 6-6 6"/>';
  }
  if (toggle){
    toggle.title = expanded ? "Collapse sidebar" : "Expand sidebar";
    var tip = toggle.querySelector(".tip");
    if (tip) tip.textContent = expanded ? "COLLAPSE" : "EXPAND";
  }
}
function toggleRailExpanded(){
  S.railExpanded = !S.railExpanded;
  localStorage.setItem("ro:railExpanded", S.railExpanded ? "1" : "0");
  applyRailExpanded();
}

/* ───────────────────────────  WIRE UP  ─────────────────────────── */
document.querySelectorAll(".rail-btn[data-page]").forEach(function(b){ b.onclick = function(){ goto(b.dataset.page); }; });
$("railToggle").onclick = toggleRailExpanded;
$("brand").onclick = backToProjects;
$("backToProjectsBtn").onclick = backToProjects;
$("crumbProject").onclick = openProjectMenu;
$("crumbApp").onclick = openAppMenu;
$("refreshBtn").onclick = function(){ withLoading(refresh); };
$("themeBtn").onclick = toggleTheme;
$("logoutBtn").onclick = logout;
$("loginForm").onsubmit = loginSubmit;
$("drawerClose").onclick = closeDrawer;
$("drawerOverlay").onclick = closeDrawer;
$("windowSelect").onchange = function(e){ S.windowMinutes = Number(e.target.value); localStorage.setItem("ro:window", String(S.windowMinutes)); withLoading(refresh); };
$("refreshSelect").onchange = function(e){ setRefresh(Number(e.target.value)); };
$("hiddenToggle").onclick = function(){ S.showHidden = !S.showHidden; render(); };
$("globalSearch").oninput = function(e){ S.searchQuery = e.target.value; render(); };
document.addEventListener("keydown", function(ev){
  if (ev.key === "Escape"){ closeDrawer(); closeMenus(); }
  if ((ev.metaKey || ev.ctrlKey) && ev.key === "k"){ ev.preventDefault(); $("globalSearch").focus(); }
  if (ev.key === "/" && document.activeElement.tagName !== "INPUT"){ ev.preventDefault(); $("globalSearch").focus(); }
});

/* expose for inline handlers */
window.RO = {selectProject, backToProjects, selectRoute, openTraceQuick, createProjectKey, showProjectKeys, deleteProject};

/* ───────────────────────────  BOOT  ─────────────────────────── */
goto("pulse");
checkAuth().then(function(ok){
  if (ok){ setRefresh(S.refreshMs); refresh(); }
});

})();
</script>
</body>
</html>
'''
