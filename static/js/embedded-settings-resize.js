(function(){
    const embeddedMode = location.search.includes('embedded=1') && new URLSearchParams(location.search).get('embedded') === '1';
    if(!embeddedMode || window.parent === window) return;

    let lastHeight = 0;
    let scheduled = false;

    function reportSize(){
        scheduled = false;
        const content = document.querySelector('.page') || document.body;
        const height = Math.ceil(Math.max(content.scrollHeight, content.getBoundingClientRect().height));
        if(!height || height === lastHeight) return;
        lastHeight = height;
        window.parent.postMessage({type: 'studio-embedded-size', height}, location.origin);
    }

    function scheduleReport(){
        if(scheduled) return;
        scheduled = true;
        requestAnimationFrame(reportSize);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const content = document.querySelector('.page') || document.body;
        new ResizeObserver(scheduleReport).observe(content);
        scheduleReport();
        window.addEventListener('load', scheduleReport, {once:true});
    }, {once:true});
})();
