(function(){
    const FALLBACK_ERROR_CODES = new Set(['api_unavailable']);
    let nativeRequestId = 0;
    const nativeRequests = new Map();

    function text(zh, en){
        return window.StudioI18n?.lang?.() === 'en' ? en : zh;
    }

    function errorMessage(payload, fallback){
        const detail = payload?.detail;
        if(typeof detail === 'string') return detail;
        return detail?.message || payload?.message || fallback;
    }

    function browserUrl(url, filename){
        const link = document.createElement('a');
        link.href = url;
        link.download = filename || '';
        link.rel = 'noopener';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
        return {ok:true, browser_fallback:true, filename:filename || '', path:''};
    }

    function browserBlob(blob, filename){
        const objectUrl = URL.createObjectURL(blob);
        const result = browserUrl(objectUrl, filename);
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
        return result;
    }

    async function parseResult(response){
        const payload = await response.json().catch(() => ({}));
        if(!response.ok){
            const error = new Error(errorMessage(payload, text('下载失败', 'Download failed')));
            error.status = response.status;
            error.code = payload?.detail?.code || payload?.code || '';
            throw error;
        }
        return payload;
    }

    function notificationEnabled(){
        try {
            const cached = JSON.parse(localStorage.getItem('studio_app_settings_cache') || '{}');
            return cached?.downloads?.notify !== false;
        } catch(_) {
            return true;
        }
    }

    function showCompletion(result){
        if(!notificationEnabled() || !result?.path) return;
        document.querySelector('.studio-download-notice')?.remove();
        const notice = document.createElement('div');
        notice.className = 'studio-download-notice';
        notice.setAttribute('role', 'status');
        notice.innerHTML = `
            <div class="studio-download-notice-icon">&#10003;</div>
            <div class="studio-download-notice-copy">
                <strong>${escapeHtml(text('下载完成', 'Download complete'))}</strong>
                <span>${escapeHtml(result.filename || '')}</span>
                <small title="${escapeHtml(result.path || '')}">${escapeHtml(result.path || '')}</small>
            </div>
            <button type="button">${escapeHtml(text('打开文件夹', 'Open folder'))}</button>`;
        notice.querySelector('button')?.addEventListener('click', () => openFolder('downloads'));
        document.body.appendChild(notice);
        requestAnimationFrame(() => notice.classList.add('visible'));
        setTimeout(() => {
            notice.classList.remove('visible');
            setTimeout(() => notice.remove(), 220);
        }, 7000);
    }

    function ensureStyles(){
        if(document.getElementById('studio-download-styles')) return;
        const style = document.createElement('style');
        style.id = 'studio-download-styles';
        style.textContent = `
            .studio-download-notice{position:fixed;right:18px;bottom:18px;z-index:100000;display:grid;grid-template-columns:30px minmax(180px,1fr) auto;align-items:center;gap:10px;width:min(520px,calc(100vw - 36px));padding:12px 14px;background:#20211f;color:#f7f7f2;border:1px solid rgba(255,255,255,.14);box-shadow:0 12px 32px rgba(0,0,0,.28);border-radius:8px;opacity:0;transform:translateY(10px);transition:opacity .2s,transform .2s;font:13px/1.35 Inter,system-ui,sans-serif}
            .studio-download-notice.visible{opacity:1;transform:none}.studio-download-notice-icon{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#2f8f5b;font-weight:800}.studio-download-notice-copy{min-width:0;display:flex;flex-direction:column;gap:2px}.studio-download-notice-copy strong{font-size:13px}.studio-download-notice-copy span,.studio-download-notice-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.studio-download-notice-copy small{color:#b8bab4;font-size:11px}.studio-download-notice button{border:1px solid rgba(255,255,255,.2);background:transparent;color:inherit;padding:7px 10px;border-radius:6px;cursor:pointer;white-space:nowrap}.studio-download-notice button:hover{background:rgba(255,255,255,.1)}
            @media(max-width:560px){.studio-download-notice{grid-template-columns:28px 1fr}.studio-download-notice button{grid-column:2;justify-self:start}}
        `;
        document.head.appendChild(style);
    }

    function escapeHtml(value){
        return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    }

    function finish(result){
        if(!result?.ok) throw new Error(result?.message || text('下载失败', 'Download failed'));
        window.dispatchEvent(new CustomEvent('studio-download-complete', {detail:result}));
        showCompletion(result);
        return result;
    }

    function shouldUseBrowserFallback(error){
        return Number(error?.status) === 404 || FALLBACK_ERROR_CODES.has(error?.code);
    }

    async function saveUrl(url, filename, category=''){
        const raw = String(url || '').trim();
        if(!raw) throw new Error(text('没有可下载的文件', 'No file to download'));
        if(raw.startsWith('blob:') || raw.startsWith('data:')){
            const response = await fetch(raw);
            if(!response.ok) throw new Error(text('读取下载内容失败', 'Failed to read download data'));
            return saveBlob(await response.blob(), filename, category);
        }
        try {
            const response = await fetch('/api/downloads/url', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({url:raw, filename:filename || 'download', category:category || ''}),
            });
            return finish(await parseResult(response));
        } catch(error) {
            if(shouldUseBrowserFallback(error)) return browserUrl(raw, filename);
            throw error;
        }
    }

    async function saveBlob(blob, filename, category=''){
        if(!(blob instanceof Blob)) throw new TypeError('saveBlob expects a Blob');
        const form = new FormData();
        form.append('file', blob, filename || 'download');
        form.append('filename', filename || 'download');
        form.append('category', category || '');
        try {
            const response = await fetch('/api/downloads/blob', {method:'POST', body:form});
            return finish(await parseResult(response));
        } catch(error) {
            if(shouldUseBrowserFallback(error)) return browserBlob(blob, filename);
            throw error;
        }
    }

    async function requestNative(action, kind=''){
        try {
            const response = await fetch('/api/desktop-action', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({action,kind,payload:{}})
            });
            const result = await response.json().catch(() => ({}));
            if(response.ok && result?.error_code !== 'desktop_api_unavailable') return result;
        } catch(error) {
            console.error('Desktop HTTP bridge failed', error);
        }
        if(window.pywebview?.api){
            if(action === 'open-directory') return window.pywebview.api.open_directory(kind);
        }
        if(window.top === window) return Promise.resolve({ok:false, error_code:'desktop_api_unavailable'});
        const id = `download-native-${Date.now()}-${++nativeRequestId}`;
        return new Promise(resolve => {
            const timer = setTimeout(() => {
                nativeRequests.delete(id);
                resolve({ok:false, error_code:'desktop_api_timeout'});
            }, 5000);
            nativeRequests.set(id, result => { clearTimeout(timer); resolve(result); });
            window.top.postMessage({type:'settings-native-request', id, action, kind}, location.origin);
        });
    }

    async function openFolder(kind='downloads'){
        return requestNative('open-directory', kind);
    }

    window.addEventListener('message', event => {
        if(event.origin !== location.origin || event.data?.type !== 'settings-native-response') return;
        const complete = nativeRequests.get(event.data.id);
        if(!complete) return;
        nativeRequests.delete(event.data.id);
        complete(event.data.result || {ok:false});
    });

    ensureStyles();
    window.StudioDownloads = {saveUrl, saveBlob, openFolder};
})();
