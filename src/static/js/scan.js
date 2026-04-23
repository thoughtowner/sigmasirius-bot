let scanning = false;
let videoStream;
let scanResult = '';

function clearScanResults() {
    scanResult = '';
    document.getElementById('scanResult').textContent = '';
    document.getElementById('resultArea').style.display = 'none';
}

async function startScanning() {
    try {
        clearScanResults();
        videoStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}});
        const video = document.getElementById('video');
        video.srcObject = videoStream;
        video.setAttribute('playsinline', true);
        video.play();
        requestAnimationFrame(tick);
        scanning = true;
        document.getElementById('toggleScanBtn').textContent = 'Stop Scanning';

        // Показать сканирующую линию
        document.getElementById('scannerLine').style.display = 'block';
    } catch (err) {
        console.error('Error accessing the camera', err);
        alert('Unable to access the camera: ' + err.message);
    }
}

function stopScanning() {
    if (videoStream) {
        const tracks = videoStream.getTracks();
        tracks.forEach(track => track.stop());
        document.getElementById('video').srcObject = null;
        scanning = false;
        document.getElementById('toggleScanBtn').textContent = 'Start Scanning';

        // Скрыть сканирующую линию
        document.getElementById('scannerLine').style.display = 'none';
    }
}

function toggleScanning() {
    if (scanning) {
        stopScanning();
    } else {
        startScanning();
    }
}

function tick() {
    if (!scanning) return;

    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.height = video.videoHeight;
        canvas.width = video.videoWidth;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert",
        });

        if (code) {
            console.log("Found QR code", code.data);
            scanResult = code.data;
            document.getElementById('scanResult').textContent = "QR Code content: " + scanResult;
            document.getElementById('resultArea').style.display = 'block';
            stopScanning();
        }
    }

    requestAnimationFrame(tick);
}

function copyResult() {
    if (scanResult) {
        navigator.clipboard.writeText(scanResult).then(() => {
            showPopup(`Вы добавили в буфер: ${scanResult}`);
        }, (err) => {
            console.error('Could not copy text: ', err);
            showPopup('Не удалось скопировать текст');
        });
    }
}

async function sendToTelegram() {
    if (scanResult) {
        const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;

        if (!userId) {
            showPopup('Не удалось определить пользователя Telegram');
            return;
        }

        let endpoint = null;
        if (scanResult.startsWith('reservation/')) {
            endpoint = '/tg/confirm-reservation/';
        } else if (scanResult.startsWith('repairman/')) {
            endpoint = '/tg/assign-repairman/';
        } else if (scanResult.startsWith('quit_as_repairman/')) {
            endpoint = '/tg/fire-repairman/';
        } else {
            showPopup('Неизвестный тип QR-кода');
            return;
        }

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    result_scan: scanResult
                }),
            });

            if (!response.ok) {
                const text = await response.text();
                throw new Error('Ошибка при отправке данных: ' + text);
            }

            const result = await response.json();
            showPopup('Успешно отправлено');
        } catch (error) {
            console.error('Ошибка:', error);
            showPopup('Ошибка при отправке данных');
        } finally {
            try {
                if (tg && typeof tg.close === 'function') tg.close();
            } catch (e) {
                console.warn('tg.close() failed', e);
            }
        }
    }
}

function showPopup(message) {
    tg.showPopup({
        title: 'Информация',
        message: message,
        buttons: [{type: 'close'}]
    });
}

// Инициализация: скрываем область результатов при загрузке страницы
// Инициализация: скрываем область результатов при загрузке страницы
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('resultArea').style.display = 'none';
    const toggleBtn = document.getElementById('toggleScanBtn');
    const confirmBtn = document.getElementById('confirmBtn');

    // Disable scanner by default until server confirms permissions
    if (toggleBtn) toggleBtn.disabled = true;
    if (confirmBtn) confirmBtn.disabled = true;

    // Verify user permissions (must have run /start and be admin)
    (async function checkPermissions() {
        try {
            const userId = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;
            if (!userId) {
                showPopup('Не удалось определить пользователя Telegram');
                return;
            }

            const resp = await fetch('/tg/check-scanner-permissions/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId})
            });

            if (!resp.ok) {
                showPopup('Ошибка проверки прав доступа');
                return;
            }

            const body = await resp.json();
            if (body.allowed) {
                if (toggleBtn) toggleBtn.disabled = false;
                if (confirmBtn) confirmBtn.disabled = false;
            } else {
                showPopup(body.message || 'Нет прав для использования сканера');
                if (toggleBtn) toggleBtn.disabled = true;
                if (confirmBtn) confirmBtn.disabled = true;
                try {
                    if (tg && typeof tg.close === 'function') tg.close();
                } catch (e) {
                    console.warn('tg.close() failed', e);
                }
                return;
            }
        } catch (err) {
            console.error('Permission check failed', err);
            showPopup('Ошибка проверки прав доступа');
            try {
                if (tg && typeof tg.close === 'function') tg.close();
            } catch (e) {
                console.warn('tg.close() failed', e);
            }
            return;
        }
    })();

    if (toggleBtn) toggleBtn.addEventListener('click', toggleScanning);
    const confirm = document.getElementById('confirmBtn');
    if (confirm) confirm.addEventListener('click', sendToTelegram);
});
