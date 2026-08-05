(function(){
    const ACTIVE_SECTION_KEY = 'settings_active_section';
    const CACHE_KEY = 'studio_app_settings_cache';
    const SECTIONS = ['downloads','appearance','language','api','workflow','storage','about'];
    const translations = {
        zh:{
            settingsTitle:'设置',downloads:'下载设置',appearance:'界面设置',language:'语言设置',apiSettings:'API 设置',workflow:'工作流设置',storage:'存储与缓存',about:'关于与更新',
            fileHandling:'文件处理',downloadDirectory:'下载目录',downloadDirectoryHint:'文件将直接保存到此目录',changeDirectory:'更改目录',restoreDefault:'恢复默认',openFolder:'打开文件夹',categorize:'按类型整理',categorizeHint:'图片、视频、音频、工作流和画布导出分别保存',sameName:'同名文件',sameNameHint:'保留原文件并自动追加序号',appendNumber:'自动追加序号',notify:'完成提醒',notifyHint:'显示文件名、保存位置和打开文件夹操作',
            visualPreferences:'视觉偏好',colorMode:'颜色模式',colorModeHint:'跟随系统会在系统外观变化时自动切换',themeSystem:'跟随系统',themeLight:'浅色',themeDark:'深色',uiScale:'界面缩放',uiScaleHint:'只调整文字和控件，不改变画布或导出尺寸',scaleAuto:'自动',contentLanguage:'内容语言',displayLanguage:'显示语言',displayLanguageHint:'切换后主界面和已打开页面立即更新',connections:'连接与模型',diskUsage:'磁盘占用',refresh:'刷新',rebuildableCache:'可重建缓存',cacheHint:'仅包含媒体预览和未完成下载的临时文件',clearCache:'清理缓存',version:'版本',manualUpdate:'手动更新',updateHint:'仅在你检查并确认后下载或安装',checkUpdate:'检查更新',downloadConnectivity:'下载源网络',notChecked:'尚未检测',probe:'检测',applicationLogs:'应用日志',logsHint:'用于排查启动、下载和更新问题',
            saved:'已保存',saveFailed:'保存失败',chooseFailed:'无法选择目录',openFailed:'无法打开文件夹',storageDirectory:'存储目录',storageDirectoryHint:'项目、素材、工作流、API 配置和日志',cacheDirectory:'缓存目录',cacheDirectoryHint:'视频封面和媒体预览缓存，可随时重建',restartRequired:'目录已修改，重新启动应用后生效',projects:'项目数据',assets:'素材',cache:'媒体预览缓存',logs:'日志',downloadFiles:'下载文件',loading:'正在读取…',cacheConfirm:'将清理 {size} 的媒体预览和未完成下载临时文件。不会删除画布、项目、素材、工作流、API 配置或日志。是否继续？',cacheDone:'已清理 {size}',noCache:'没有可清理的缓存',checking:'正在检查…',upToDate:'当前已是最新版本',updateAvailable:'发现新版本 {version}',installUpdate:'下载并安装更新',installConfirm:'将下载并启动 {version} 完整安装包，安装时应用会关闭。是否继续？',updating:'正在下载安装包…',updateDone:'安装包已启动',networkAvailable:'可用',networkUnavailable:'不可用',requestFailed:'请求失败'
        },
        en:{
            settingsTitle:'Settings',downloads:'Downloads',appearance:'Appearance',language:'Language',apiSettings:'API Settings',workflow:'Workflow',storage:'Storage & Cache',about:'About & Updates',
            fileHandling:'File handling',downloadDirectory:'Download folder',downloadDirectoryHint:'Files are saved directly to this folder',changeDirectory:'Change folder',restoreDefault:'Restore default',openFolder:'Open folder',categorize:'Organize by type',categorizeHint:'Separate images, videos, audio, workflows, and canvas exports',sameName:'Duplicate names',sameNameHint:'Keep the original and append a number',appendNumber:'Append a number',notify:'Completion notification',notifyHint:'Show the file name, saved location, and open-folder action',
            visualPreferences:'Visual preferences',colorMode:'Color mode',colorModeHint:'System mode follows operating system appearance changes',themeSystem:'Use system',themeLight:'Light',themeDark:'Dark',uiScale:'Interface scale',uiScaleHint:'Adjusts text and controls without changing canvas or export sizes',scaleAuto:'Auto',contentLanguage:'Content language',displayLanguage:'Display language',displayLanguageHint:'Updates the main interface and loaded pages immediately',connections:'Connections & models',diskUsage:'Disk usage',refresh:'Refresh',rebuildableCache:'Rebuildable cache',cacheHint:'Media previews and unfinished download temporary files only',clearCache:'Clear cache',version:'Version',manualUpdate:'Manual updates',updateHint:'Downloads or installs only after you check and confirm',checkUpdate:'Check for updates',downloadConnectivity:'Download source network',notChecked:'Not checked',probe:'Probe',applicationLogs:'Application logs',logsHint:'Used to diagnose startup, download, and update problems',
            saved:'Saved',saveFailed:'Save failed',chooseFailed:'Could not choose a folder',openFailed:'Could not open folder',storageDirectory:'Storage folder',storageDirectoryHint:'Projects, assets, workflows, API configuration, and logs',cacheDirectory:'Cache folder',cacheDirectoryHint:'Rebuildable video posters and media previews',restartRequired:'Folder changed. Restart the app to apply it.',projects:'Project data',assets:'Assets',cache:'Media preview cache',logs:'Logs',downloadFiles:'Downloads',loading:'Loading…',cacheConfirm:'Clear {size} of media previews and unfinished download files? Canvases, projects, assets, workflows, API configuration, and logs are excluded.',cacheDone:'Cleared {size}',noCache:'No cache to clear',checking:'Checking…',upToDate:'You are up to date',updateAvailable:'Version {version} is available',installUpdate:'Download and install',installConfirm:'Download and launch the full {version} installer? The app will close during installation.',updating:'Downloading installer…',updateDone:'Installer launched',networkAvailable:'Available',networkUnavailable:'Unavailable',requestFailed:'Request failed'
        }
    };
    const storageIcons = {projects:'folder-kanban',assets:'library',cache:'images',logs:'scroll-text',downloads:'download'};
    const storageLabels = {projects:'projects',assets:'assets',cache:'cache',logs:'logs',downloads:'downloadFiles'};
    let settings = null;
    let currentUpdate = null;
    let nativeSequence = 0;
    const nativePending = new Map();
    const embeddedTopResetTimers = new WeakMap();

    function currentLanguage(){ return settings?.language || window.StudioI18n?.lang?.() || 'zh'; }
    function t(key, values={}){
        let value = translations[currentLanguage()]?.[key] || translations.zh[key] || key;
        Object.entries(values).forEach(([name,replacement]) => { value = value.replace(`{${name}}`, replacement); });
        return value;
    }
    function escapeHtml(value){ return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
    function localize(){
        document.documentElement.lang = currentLanguage() === 'en' ? 'en' : 'zh-CN';
        document.querySelectorAll('[data-l10n]').forEach(node => { node.textContent = t(node.dataset.l10n); });
        document.querySelectorAll('[data-l10n-title]').forEach(node => { node.title = t(node.dataset.l10nTitle); });
    }
    async function requestJson(url, options={}){
        const response = await fetch(url, options);
        const payload = await response.json().catch(() => ({}));
        if(!response.ok){
            const detail = payload?.detail;
            throw new Error((typeof detail === 'string' ? detail : detail?.message) || payload?.message || t('requestFailed'));
        }
        return payload;
    }
    function cacheSettings(){
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(settings)); } catch(_) {}
    }
    function showStatus(message, error=false){
        const node = document.getElementById('settingsSaveStatus');
        if(!node) return;
        node.textContent = message;
        node.classList.toggle('error', error);
        clearTimeout(showStatus.timer);
        showStatus.timer = setTimeout(() => { node.textContent = ''; node.classList.remove('error'); }, 2600);
    }
    function legacyPatch(){
        const theme = localStorage.getItem('studio_theme') || localStorage.getItem('canvas_theme') || 'system';
        const scale = localStorage.getItem('studio_ui_scale_mode') || 'auto';
        const language = localStorage.getItem('studio_lang') || 'zh';
        return {appearance:{theme,scale},language};
    }
    function broadcastPreferences(){
        const detail = {appearance:{...settings.appearance}, language:settings.language};
        window.parent.postMessage({type:'studio-settings-preferences', settings:detail}, location.origin);
        document.querySelectorAll('.embedded-frame-wrap iframe').forEach(syncEmbeddedFrame);
    }
    function applyPreferences(){
        localStorage.setItem('studio_theme', settings.appearance.theme);
        localStorage.setItem('canvas_theme', settings.appearance.theme);
        localStorage.setItem('studio_ui_scale_mode', settings.appearance.scale);
        localStorage.setItem('studio_lang', settings.language);
        window.StudioTheme?.set?.(settings.appearance.theme);
        window.StudioScale?.set?.(settings.appearance.scale);
        window.StudioI18n?.set?.(settings.language);
        localize();
        broadcastPreferences();
    }
    function renderChoices(){
        document.querySelectorAll('[data-setting-choice="theme"] button').forEach(button => button.classList.toggle('active', button.dataset.value === settings.appearance.theme));
        document.querySelectorAll('[data-setting-choice="scale"] button').forEach(button => button.classList.toggle('active', button.dataset.value === settings.appearance.scale));
        document.querySelectorAll('[data-setting-choice="language"] button').forEach(button => button.classList.toggle('active', button.dataset.value === settings.language));
    }
    function renderSettings(){
        const directory = settings.downloads.resolved_directory || settings.downloads.directory || '';
        const output = document.getElementById('downloadDirectory');
        output.textContent = directory; output.title = directory;
        document.getElementById('downloadCategorize').checked = settings.downloads.categorize !== false;
        document.getElementById('downloadNotify').checked = settings.downloads.notify !== false;
        renderChoices(); cacheSettings(); localize();
        window.lucide?.createIcons?.();
    }
    async function persist(patch){
        const previous = JSON.parse(JSON.stringify(settings));
        try {
            settings = await requestJson('/api/app-settings', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
            renderSettings(); applyPreferences(); showStatus(t('saved'));
            return settings;
        } catch(error) {
            settings = previous; renderSettings(); applyPreferences(); showStatus(`${t('saveFailed')}: ${error.message}`, true); throw error;
        }
    }
    async function loadSettings(){
        settings = await requestJson('/api/app-settings');
        if(settings.migration_needed){ settings = await requestJson('/api/app-settings', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(legacyPatch())}); }
        renderSettings(); applyPreferences();
    }
    function activateSection(section){
        const next = SECTIONS.includes(section) ? section : 'downloads';
        localStorage.setItem(ACTIVE_SECTION_KEY, next);
        const content = document.querySelector('.settings-content');
        if(content) content.scrollTop = 0;
        document.querySelectorAll('[data-settings-section]').forEach(button => button.classList.toggle('active', button.dataset.settingsSection === next));
        document.querySelectorAll('[data-settings-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.settingsPanel === next));
        const panel = document.querySelector(`[data-settings-panel="${next}"]`);
        const frame = panel?.querySelector('iframe[data-embedded-src]');
        if(frame){
            frame.dataset.resetScrollTop = '1';
            clearTimeout(embeddedTopResetTimers.get(frame));
            embeddedTopResetTimers.set(frame, setTimeout(() => { delete frame.dataset.resetScrollTop; }, 1500));
            if(!frame.src) frame.src = frame.dataset.embeddedSrc;
        }
        if(next === 'storage') refreshStorage();
        if(next === 'about') loadAbout();
        requestAnimationFrame(() => window.lucide?.createIcons?.());
    }
    async function directNativeRequest(action, kind='', payload={}){
        const api = window.top?.pywebview?.api || window.pywebview?.api;
        if(!api) return null;
        if(action === 'choose-download-directory') return api.choose_download_directory();
        if(action === 'choose-directory') return api.choose_directory(kind);
        if(action === 'open-directory') return api.open_directory(kind);
        if(action === 'install-update') return api.install_update(payload.url || '', payload.version || '');
        return {ok:false,error_code:'desktop_action_unknown'};
    }
    async function requestNative(action, kind='', payload={}){
        try {
            const direct = await directNativeRequest(action, kind, payload);
            if(direct) return direct;
        } catch(_) {}
        const id = `settings-native-${Date.now()}-${++nativeSequence}`;
        return new Promise(resolve => {
            const timer = setTimeout(() => { nativePending.delete(id); resolve({ok:false,error_code:'desktop_api_timeout'}); }, 8000);
            nativePending.set(id, result => { clearTimeout(timer); resolve(result); });
            window.parent.postMessage({type:'settings-native-request',id,action,kind,payload}, location.origin);
        });
    }
    async function chooseDownloadDirectory(){
        const result = await requestNative('choose-download-directory');
        if(result?.cancelled) return;
        if(!result?.ok){ showStatus(t('chooseFailed'), true); return; }
        settings = result.settings || await requestJson('/api/app-settings');
        renderSettings();
    }
    async function openDirectory(kind){
        const result = await requestNative('open-directory', kind);
        if(!result?.ok) showStatus(t('openFailed'), true);
    }
    async function chooseDirectory(kind){
        const result = await requestNative('choose-directory', kind);
        if(result?.cancelled) return;
        if(!result?.ok){ showStatus(t('chooseFailed'), true); return; }
        showStatus(result.restart_required ? t('restartRequired') : t('saved'));
        await refreshStorage();
    }
    function formatBytes(value){
        const bytes = Math.max(0, Number(value) || 0);
        if(bytes < 1024) return `${bytes} B`;
        const units = ['KB','MB','GB','TB']; let amount = bytes; let index = -1;
        do { amount /= 1024; index++; } while(amount >= 1024 && index < units.length - 1);
        return `${amount >= 10 ? amount.toFixed(1) : amount.toFixed(2)} ${units[index]}`;
    }
    async function refreshStorage(){
        const list = document.getElementById('storageList');
        list.innerHTML = `<div class="storage-row"><div></div><div class="storage-row-copy"><span>${escapeHtml(t('loading'))}</span></div></div>`;
        try {
            const report = await requestJson('/api/storage-report');
            const storageOutput = document.getElementById('storageDirectory');
            const cacheOutput = document.getElementById('cacheDirectory');
            if(storageOutput){ storageOutput.textContent = report.roots?.data || ''; storageOutput.title = report.roots?.data || ''; }
            if(cacheOutput){ cacheOutput.textContent = report.roots?.cache || ''; cacheOutput.title = report.roots?.cache || ''; }
            list.innerHTML = report.entries.map(entry => `
                <div class="storage-row">
                    <i data-lucide="${storageIcons[entry.kind] || 'folder'}"></i>
                    <div class="storage-row-copy"><strong>${escapeHtml(t(storageLabels[entry.kind] || entry.kind))}</strong><span title="${escapeHtml(entry.path)}">${escapeHtml(entry.path)}</span></div>
                    <span class="storage-size">${formatBytes(entry.bytes)}</span>
                    <button class="icon-command" type="button" data-open-directory="${escapeHtml(entry.kind === 'projects' ? 'data' : entry.kind)}" title="${escapeHtml(t('openFolder'))}"><i data-lucide="folder-open"></i></button>
                </div>`).join('');
            const preview = await requestJson('/api/cache-cleanup-preview');
            document.getElementById('cacheSize').textContent = formatBytes(preview.bytes);
            window.lucide?.createIcons?.();
        } catch(error) { list.innerHTML = `<div class="update-result">${escapeHtml(error.message)}</div>`; }
    }
    async function clearCache(){
        const preview = await requestJson('/api/cache-cleanup-preview');
        if(!preview.bytes){ showStatus(t('noCache')); return; }
        if(!confirm(t('cacheConfirm',{size:formatBytes(preview.bytes)}))) return;
        const result = await requestJson('/api/cache-cleanup',{method:'POST'});
        showStatus(t('cacheDone',{size:formatBytes(result.removed_bytes)}));
        await refreshStorage();
    }
    async function loadAbout(){
        try { const info = await requestJson('/api/app-info'); document.getElementById('appVersion').textContent = info.version || '--'; } catch(_) {}
    }
    function renderUpdate(result){
        currentUpdate = result?.best || null;
        const box = document.getElementById('updateResult'); box.hidden = false;
        if(!result.update_available){ box.innerHTML = `<strong>${escapeHtml(t('upToDate'))}</strong>`; return; }
        const version = currentUpdate?.version || '';
        box.innerHTML = `<strong>${escapeHtml(t('updateAvailable',{version}))}</strong><br>${escapeHtml(currentUpdate?.update_notes?.items?.map(item => item.text).filter(Boolean).join(' · ') || '')}<br><button class="command primary" type="button" id="installUpdate"><i data-lucide="download-cloud"></i><span>${escapeHtml(t('installUpdate'))}</span></button>`;
        document.getElementById('installUpdate').addEventListener('click', installUpdate);
        window.lucide?.createIcons?.();
    }
    async function checkUpdate(){
        const button = document.getElementById('checkUpdate'); button.disabled = true;
        document.getElementById('updateSummary').textContent = t('checking');
        try { const result = await requestJson('/api/check-update'); renderUpdate(result); document.getElementById('updateSummary').textContent = result.update_available ? t('updateAvailable',{version:result.best?.version || ''}) : t('upToDate'); }
        catch(error){ document.getElementById('updateSummary').textContent = error.message; }
        finally { button.disabled = false; }
    }
    async function installUpdate(){
        const version = currentUpdate?.version || '';
        if(!currentUpdate || !confirm(t('installConfirm',{version}))) return;
        const button = document.getElementById('installUpdate'); if(button) button.disabled = true;
        document.getElementById('updateSummary').textContent = t('updating');
        try { const result = await requestNative('install-update', '', {url:currentUpdate.installer_url || '', version}); if(!result?.ok) throw new Error(result?.message || result?.error_code || t('requestFailed')); document.getElementById('updateSummary').textContent = t('updateDone'); }
        catch(error){ document.getElementById('updateSummary').textContent = error.message; if(button) button.disabled = false; }
    }
    async function probeConnectivity(){
        const summary = document.getElementById('connectivitySummary'); summary.textContent = t('checking');
        try { const result = await requestJson('/api/update-connectivity'); const available = Boolean(result.ok || result.github?.ok || result.modelscope?.ok || result.targets?.some?.(item => item.ok)); summary.textContent = available ? t('networkAvailable') : t('networkUnavailable'); }
        catch(error){ summary.textContent = error.message; }
    }
    function syncEmbeddedFrame(frame){
        if(!frame?.contentWindow || !settings) return;
        const resolvedTheme = window.StudioTheme?.getResolved?.() || (document.documentElement.classList.contains('studio-theme-dark') ? 'dark' : 'light');
        frame.contentWindow.postMessage({type:'studio-theme',theme:resolvedTheme,mode:settings.appearance.theme}, location.origin);
        frame.contentWindow.postMessage({type:'studio-ui-scale',mode:settings.appearance.scale,scale:window.StudioScale?.getScale?.() || 1}, location.origin);
        frame.contentWindow.postMessage({type:'studio-lang',lang:settings.language}, location.origin);
    }
    function bindEvents(){
        document.querySelectorAll('[data-settings-section]').forEach(button => button.addEventListener('click', () => activateSection(button.dataset.settingsSection)));
        document.getElementById('changeDownloadDirectory').addEventListener('click', chooseDownloadDirectory);
        document.getElementById('resetDownloadDirectory').addEventListener('click', () => persist({downloads:{directory:''}}));
        document.getElementById('downloadCategorize').addEventListener('change', event => persist({downloads:{categorize:event.target.checked}}));
        document.getElementById('downloadNotify').addEventListener('change', event => persist({downloads:{notify:event.target.checked}}));
        document.querySelectorAll('[data-setting-choice="theme"] button').forEach(button => button.addEventListener('click', () => persist({appearance:{theme:button.dataset.value}})));
        document.querySelectorAll('[data-setting-choice="scale"] button').forEach(button => button.addEventListener('click', () => persist({appearance:{scale:button.dataset.value}})));
        document.querySelectorAll('[data-setting-choice="language"] button').forEach(button => button.addEventListener('click', () => persist({language:button.dataset.value})));
        document.body.addEventListener('click', event => { const button = event.target.closest('[data-open-directory]'); if(button) openDirectory(button.dataset.openDirectory); });
        document.body.addEventListener('click', event => { const button = event.target.closest('[data-choose-directory]'); if(button) chooseDirectory(button.dataset.chooseDirectory); });
        document.getElementById('refreshStorage').addEventListener('click', refreshStorage);
        document.getElementById('clearCache').addEventListener('click', clearCache);
        document.getElementById('checkUpdate').addEventListener('click', checkUpdate);
        document.getElementById('probeConnectivity').addEventListener('click', probeConnectivity);
        document.querySelectorAll('.embedded-frame-wrap iframe').forEach(frame => frame.addEventListener('load', () => syncEmbeddedFrame(frame)));
        window.addEventListener('message', event => {
            if(event.origin !== location.origin) return;
            if(event.data?.type === 'studio-embedded-size'){
                const frame = Array.from(document.querySelectorAll('.embedded-frame-wrap iframe')).find(frame => frame.contentWindow === event.source);
                if(!frame) return;
                const height = Math.min(24000, Math.max(320, Math.ceil(Number(event.data.height) || 0)));
                frame.style.setProperty('--embedded-frame-height', `${height}px`);
                if(frame.dataset.resetScrollTop === '1'){
                    const content = document.querySelector('.settings-content');
                    if(content) content.scrollTop = 0;
                }
            }
            if(event.data?.type === 'settings-native-response'){
                const complete = nativePending.get(event.data.id); if(!complete) return;
                nativePending.delete(event.data.id); complete(event.data.result || {ok:false});
            }
            if(event.data?.type === 'studio-theme' || event.data?.type === 'studio-ui-scale' || event.data?.type === 'studio-lang'){
                document.querySelectorAll('.embedded-frame-wrap iframe').forEach(frame => { try { frame.contentWindow?.postMessage(event.data, location.origin); } catch(_) {} });
            }
        });
    }
    async function start(){
        bindEvents(); activateSection(localStorage.getItem(ACTIVE_SECTION_KEY) || 'downloads');
        try { await loadSettings(); } catch(error) { showStatus(error.message, true); }
        window.lucide?.createIcons?.();
    }
    document.addEventListener('DOMContentLoaded', start, {once:true});
})();
