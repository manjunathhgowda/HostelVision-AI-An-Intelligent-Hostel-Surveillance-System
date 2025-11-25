document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video');
    const cameraOverlay = document.getElementById('cameraOverlay');
    const startBtn = document.getElementById('startAttendance');
    const statusDiv = document.getElementById('attendanceStatus');
    const presentTable = document.getElementById('presentTable');
    let stream;
    let intervalId;

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
    if (!presentTable) {
        console.error('Present table element not found');
        statusDiv.innerHTML = '<div class="text-danger">Error: Present table not found</div>';
        return;
    }
    console.log('DOM loaded, elements found:', { video, cameraOverlay, startBtn, statusDiv, presentTable });

    // Check video visibility
    if (video.offsetParent === null) {
        console.warn('Video element is not visible in the DOM');
        statusDiv.innerHTML = '<div class="text-danger">Error: Video element is hidden</div>';
    }

    // Fetch and update attendance table
    function updateAttendanceTable() {
        console.log('Updating attendance table...');
        if (!presentTable) {
            console.error('Present table not found during update');
            statusDiv.innerHTML = '<div class="text-danger">Error: Present table not found</div>';
            return;
        }
        fetch('/attendance')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.text();
            })
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newTableBody = doc.querySelector('#presentTable tbody');
                if (newTableBody) {
                    const tbody = presentTable.querySelector('tbody');
                    if (tbody) {
                        tbody.innerHTML = newTableBody.innerHTML;
                        console.log('Attendance table updated successfully');
                    } else {
                        console.error('Table body not found in presentTable');
                        statusDiv.innerHTML = '<div class="text-danger">Error: Table body not found</div>';
                    }
                } else {
                    console.error('Table body not found in response HTML');
                    statusDiv.innerHTML = '<div class="text-danger">Error: Table body not found in response</div>';
                }
            })
            .catch(err => {
                console.error('Error updating attendance table:', err);
                statusDiv.innerHTML = `<div class="text-danger">Error updating table: ${err.message}</div>`;
            });
    }

    startBtn.addEventListener('click', function() {
        console.log('Start Attendance button clicked');
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
                                processAttendance();
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

    // Add Stop Attendance button
    startBtn.insertAdjacentHTML('afterend', 
        '<button id="stopAttendance" class="btn btn-danger mt-3 ms-2">Stop Attendance</button>'
    );
    const stopBtn = document.getElementById('stopAttendance');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            console.log('Stop Attendance button clicked');
            clearInterval(intervalId);
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                video.srcObject = null;
                console.log('Camera stream stopped');
            }
            cameraOverlay.style.display = 'block';
            startBtn.disabled = false;
            statusDiv.innerHTML = '<div class="text-info">Camera stopped</div>';
        });
    } else {
        console.error('Stop Attendance button not found');
    }

    function processAttendance() {
        console.log('Starting attendance processing...');
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');

        intervalId = setInterval(() => {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('image', blob, 'frame.jpg');

                console.log('Sending image to /process_attendance');
                fetch('/process_attendance', {
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
                    console.log('Attendance response:', data);
                    const statusClass = data.status === 'success' ? 'text-success' : 'text-danger';
                    statusDiv.innerHTML = data.message
                        .split('; ')
                        .map(msg => `<div class="${statusClass}">${msg}</div>`)
                        .join('');
                    if (data.status === 'success') {
                        updateAttendanceTable();
                    }
                })
                .catch(err => {
                    console.error('Process attendance error:', err);
                    statusDiv.innerHTML = `<div class="text-danger">Error: ${err.message}</div>`;
                });
            }, 'image/jpeg', 0.9);
        }, 5000);
    }

    // Periodically refresh table every 30 seconds
    setInterval(updateAttendanceTable, 30000);

    // Initial table load
    updateAttendanceTable();
});