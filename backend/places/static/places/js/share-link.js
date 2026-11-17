document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-share-store]').forEach(function (button) {
        button.addEventListener('click', async function () {
            const url = new URL(button.dataset.shareUrl, window.location.origin).href;
            const status = button.parentElement.parentElement.querySelector('[data-share-status]');
            status.textContent = '';

            try {
                if (navigator.share) {
                    await navigator.share({
                        title: button.dataset.shareTitle,
                        url: url,
                    });
                    status.textContent = 'Store link shared.';
                } else if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(url);
                    status.textContent = 'Store link copied. You can paste it to share.';
                } else {
                    status.textContent = 'Could not share the link in this browser.';
                }
            } catch (error) {
                if (error.name !== 'AbortError') {
                    status.textContent = 'Could not share the link. Copy it from the address bar.';
                }
            }
        });
    });
});
