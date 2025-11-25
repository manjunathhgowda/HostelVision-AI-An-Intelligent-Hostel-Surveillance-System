document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video');
    const cameraOverlay = document.getElementById('cameraOverlay');
    const startBtn = document.getElementById('startMonitoring');
    const statusDiv = document.getElementById('monitorStatus');
    const visitorTable = document.getElementById('visitorTable');
    let stream;
    let intervalId;
    let lastDebugImage = null;


    // Validate critical elements
    if (!video) {
        console.error('Video element not found');
        statusDiv.innerHTML = '<div class="text-danger">Error: Video element not found</div>';
        return;
    }
    if (!cameraOverlay) {
        console.error('Camera overlay image not found');
        statusDiv.innerHTML = '<div class="text-danger">Error: Camera overlay image not found</div>';
        return;
    }
    if (!startBtn) {
        console.error('Start button element not found');
        statusDiv.innerHTML = '<div class="text-danger">Error: Start button not found</div>';
        return;
    }
    if (!statusDiv) {
        console.error('Status div element not found');
        return;
    }
    if (!visitorTable) {
        console.error('Visitor table element not found');
        statusDiv.innerHTML = '<div class="text-danger">Error: Visitor table not found</div>';
        return;
    }
    console.log('DOM loaded, elements found:', { video, cameraOverlay, startBtn, statusDiv, visitorTable });

    // Check video visibility
    if (video.offsetParent === null) {
        console.warn('Video element is not visible in the DOM');
        statusDiv.innerHTML = '<div class="text-danger">Error: Video element is hidden</div>';
    }

    // Fetch and update visitor table
    function updateVisitorTable() {
        console.log('Updating visitor table...');
        if (!visitorTable) {
            console.error('Visitor table not found during update');
            statusDiv.innerHTML = '<div class="text-danger">Error: Visitor table not found</div>';
            return;
        }
        fetch('/intrusion-monitor')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.text();
            })
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newTableBody = doc.querySelector('#visitorTable tbody');
                if (newTableBody) {
                    const tbody = visitorTable.querySelector('tbody');
                    if (tbody) {
                        tbody.innerHTML = newTableBody.innerHTML;
                        console.log('Visitor table updated successfully');
                    } else {
                        console.error('Table body not found in visitorTable');
                        statusDiv.innerHTML = '<div class="text-danger">Error: Table body not found</div>';
                    }
                } else {
                    console.error('Table body not found in response HTML');
                    statusDiv.innerHTML = '<div class="text-danger">Error: Table body not found in response</div>';
                }
            })
            .catch(err => {
                console.error('Error updating visitor table:', err);
                statusDiv.innerHTML = `<div class="text-danger">Error updating table: ${err.message}</div>`;
            });
    }

    startBtn.addEventListener('click', function() {
        console.log('Start Monitoring button clicked');
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            statusDiv.innerHTML = '<div class="text-danger">Camera not supported by this browser</div>';
            startBtn.disabled = false;
            console.error('Camera not supported by browser');
            return;
        }
        startBtn.disabled = true;
        statusDiv.innerHTML = '<div class="text-info">Starting camera...</div>';

        navigator.mediaDevices.getUserMedia({ video: true })
            .then(s => {
                console.log('Stream received:', s.getVideoTracks());
                stream = s;
                video.srcObject = stream;
                video.play()
                    .then(() => {
                        console.log('Video playback started');
                        // Hide overlay image
                        cameraOverlay.style.display = 'none';
                        statusDiv.innerHTML = '<div class="text-success">Camera started successfully</div>';
                        // Verify video is displaying
                        setTimeout(() => {
                            if (video.videoWidth === 0 || video.videoHeight === 0) {
                                console.error('Video stream not displaying');
                                statusDiv.innerHTML = '<div class="text-danger">Error: Camera stream not displaying</div>';
                                stream.getTracks().forEach(track => track.stop());
                                video.srcObject = null;
                                cameraOverlay.style.display = 'block';
                                startBtn.disabled = false;
                            } else {
                                console.log('Video stream confirmed displaying');
                                processMonitoring();
                            }
                        }, 1000);
                    })
                    .catch(err => {
                        console.error('Video play error:', err.name, err.message);
                        statusDiv.innerHTML = `<div class="text-danger">Video play error: ${err.name} - ${err.message}</div>`;
                        cameraOverlay.style.display = 'block';
                        startBtn.disabled = false;
                    });
            })
            .catch(err => {
                console.error('Camera error:', err.name, err.message);
                statusDiv.innerHTML = `<div class="text-danger">Camera error: ${err.name} - ${err.message}</div>`;
                cameraOverlay.style.display = 'block';
                startBtn.disabled = false;
            });
    });

    // Add Stop Monitoring button
    startBtn.insertAdjacentHTML('afterend', 
        '<button id="stopMonitoring" class="btn btn-danger mt-3 ms-2">Stop Monitoring</button>'
    );
    const stopBtn = document.getElementById('stopMonitoring');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            console.log('Stop Monitoring button clicked');
            clearInterval(intervalId);
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                video.srcObject.over = null;
                console.log('Camera stream stopped');
            }
            cameraOverlay.style.display = 'block';
            startBtn.disabled = false;
            statusDiv.innerHTML = '<div class="text-info">Camera stopped</div>';
        });
    } else {
        console.error('Stop Monitoring button not found');
    }

    function processMonitoring() {
        console.log('Starting monitoring processing...');
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 320;
        canvas.height = video.videoHeight || 240;
        const ctx = canvas.getContext('2d');

        intervalId = setInterval(() => {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('image', blob, 'frame.jpg');

                console.log('Sending image to /process_intrusion');
                fetch('/process_intrusion', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                    .then(data => {
                    console.log('Monitoring response:', data);
                    const statusClass = data.status === 'success' ? 'text-success' : 'text-danger';
                    statusDiv.innerHTML = data.message
                        .split('; ')
                        .map(msg => `<div class="${statusClass}">${msg}</div>`)
                        .join('');
                    if (data.debug_image && data.debug_image !== lastDebugImage) {
                        lastDebugImage = data.debug_image;
                        const timestamp = new Date().getTime();
                        const debugOverlay = document.getElementById('debugOverlay');
                        debugOverlay.src = data.debug_image + `?t=${timestamp}`;
                        debugOverlay.style.display = 'block';
                    }
                    if (data.status === 'success') {
                        updateVisitorTable();
                    }
                })
                .catch(err => {
                    console.error('Process monitoring error:', err);
                    statusDiv.innerHTML = `<div class="text-danger">Error: ${err.message}</div>`;
                });
            }, 'image/jpeg', 0.9);
        }, 8000);
    }

    // Periodically refresh table every 30 seconds
    setInterval(updateVisitorTable, 30000);

    // Initial table load
    updateVisitorTable();
});