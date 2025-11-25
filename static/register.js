let captureCount = 0;
const MIN_CAPTURES = 20;
let capturedImages = [];
let videoStream;
let selectedFiles = [];

document.addEventListener('DOMContentLoaded', function() {
    initializeFileUpload();
    addEventListeners();
    addRippleEffect();
    addNavbarScrollEffect();
    generateUserID();
    const userRoleSelect = document.getElementById('userRole');
    if (userRoleSelect) {
        userRoleSelect.addEventListener('change', generateUserID);
    }
});

function resetForm() {
    const form = document.getElementById('registerForm');
    form.reset();
    selectedFiles = [];
    captureCount = 0;
    capturedImages = [];
    document.getElementById('profilePic').classList.remove('show');
    document.querySelector('.profile-pic-overlay').style.display = 'block';
    document.getElementById('previewContainer').innerHTML = '';
    document.getElementById('uploadPreviewContainer').innerHTML = '';
    document.getElementById('captureInfo').innerHTML = 'Captures remaining: 20';
    document.getElementById('uploadInfo').style.display = 'none';
    document.getElementById('uploadPreviewContainer').style.display = 'none';
    document.getElementById('captureBtn').innerHTML = '<i class="fas fa-camera"></i> Capture Photo (1/20)';
    document.getElementById('captureBtn').disabled = false;
    document.getElementById('submitBtn').disabled = true;
    stopCamera();
    generateUserID(); // Refresh user ID based on current role
}

//validation 

function addFieldValidations() {
    const fields = [
        {
            id: 'userRole',
            errorId: 'roleError',
            message: 'Role is required',
            validate: value => value !== ''
        },
        {
            id: 'hosteliteName',
            errorId: 'nameError',
            message: 'Name is required',
            validate: value => value.trim() !== ''
        },
        {
            id: 'age',
            errorId: 'ageError',
            message: 'Valid age is required (10-60)',
            validate: value => value && !isNaN(value) && value > 9 && value <= 60
        },
        {
            id: 'contact',
            errorId: 'contactError',
            message: 'Valid contact number is required (10 digits)',
            validate: value => /^\d{10}$/.test(value)
        },
        {
            id: 'email',
            errorId: 'emailError',
            message: 'Valid email is required',
            validate: value => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
        }
    ];

    fields.forEach(field => {
        const input = document.getElementById(field.id);
        const errorElement = document.getElementById(field.errorId);

        if (input && errorElement) {
            input.addEventListener('blur', () => {
                const value = input.value;
                if (!field.validate(value)) {
                    errorElement.textContent = field.message;
                } else {
                    errorElement.textContent = '';
                }
            });

            // Clear error on input
            input.addEventListener('input', () => {
                errorElement.textContent = '';
            });
        }
    });
}

// Call the validation function when DOM is loaded
document.addEventListener('DOMContentLoaded', addFieldValidations);

function displayProfilePic(input) {
    const file = input.files[0];
    const preview = document.getElementById('profilePic');

    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function (e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        preview.src = '';
        preview.style.display = 'none';
    }
}

function togglePhotoMethod() {
    const method = document.querySelector('input[name="photo_method"]:checked').value;
    const camera = document.getElementById('camera-container');
    const upload = document.getElementById('upload-container');
    const submitBtn = document.getElementById('submitBtn');
    if (method === 'camera') {
        camera.style.display = 'block';
        upload.style.display = 'none';
        startCamera();
        submitBtn.disabled = true;
        resetCapture();
    } else {
        camera.style.display = 'none';
        upload.style.display = 'block';
        stopCamera();
        checkUploadSubmitState();
    }
}

function startCamera() {
    const video = document.getElementById('video');
    navigator.mediaDevices.getUserMedia({ 
        video: { 
            width: { ideal: 640 },
            height: { ideal: 480 }
        } 
    })
    .then(stream => {
        videoStream = stream;
        video.srcObject = stream;
    })
    .catch(err => {
        alert("Camera not available: " + err);
        console.error("Camera error:", err);
    });
}

function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
}

function resetCapture() {
    captureCount = 0;
    capturedImages = [];
    renderCameraPreview();
    updateCaptureUI();
    document.getElementById('captureBtn').innerHTML = '<i class="fas fa-camera"></i> Capture Photo (1/20)';
    document.getElementById('captureBtn').disabled = false;
    document.getElementById('captured_images').value = '';
    document.getElementById('submitBtn').disabled = true;
}

function capturePhoto() {
    const canvas = document.getElementById('canvas');
    const video = document.getElementById('video');
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function(blob) {
        if (!blob) return;
        capturedImages.push(blob);
        captureCount++;
        renderCameraPreview(blob);
        updateCaptureUI();
    }, 'image/jpeg', 0.9);
}

function renderCameraPreview(dataURL) {
    const previewContainer = document.getElementById('previewContainer');
    previewContainer.innerHTML = '';
    if (capturedImages.length === 0) {
        return;
    }
    previewContainer.className = 'preview-container';
    previewContainer.style.cssText = `
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
        gap: 10px;
        margin-top: 20px;
        padding: 20px;
        background: rgba(255, 255, 255, 0.5);
        border-radius: 15px;
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        max-height: 300px;
        overflow-y: auto;
    `;
    capturedImages.forEach((dataURL, index) => {
        const container = document.createElement('div');
        container.style.cssText = `
            position: relative;
            width: 80px;
            height: 80px;
        `;
        const img = document.createElement('img');
        const objectURL = URL.createObjectURL(dataURL);
        img.src = objectURL;
        img.alt = `Captured ${index + 1}`;
        img.title = `Captured Photo ${index + 1}`;
        img.style.cssText = `
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 10px;
            border: 2px solid #667eea;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        `;
        const removeBtn = document.createElement('button');
        removeBtn.innerHTML = '×';
        removeBtn.style.cssText = `
            position: absolute;
            top: -5px;
            right: -5px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: none;
            background: #ff4757;
            color: white;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
        `;
        removeBtn.onclick = () => removeCapturedImage(index);
        container.addEventListener('mouseenter', () => {
            img.style.transform = 'scale(1.1)';
            img.style.boxShadow = '0 5px 15px rgba(0, 0, 0, 0.2)';
            img.style.zIndex = '5';
        });
        container.addEventListener('mouseleave', () => {
            img.style.transform = 'scale(1)';
            img.style.boxShadow = 'none';
            img.style.zIndex = '1';
        });
        img.addEventListener('click', () => {
            showImageModal(dataURL, `Captured Photo ${index + 1}`);
        });
        container.appendChild(img);
        container.appendChild(removeBtn);
        previewContainer.appendChild(container);
    });
}

function removeCapturedImage(index) {
    capturedImages.splice(index, 1);
    captureCount--;
    renderCameraPreview();
    updateCaptureUI();
}

function updateCaptureUI() {
    const captureInfo = document.getElementById('captureInfo');
    const captureBtn = document.getElementById('captureBtn');
    const submitBtn = document.getElementById('submitBtn');
    const remaining = MIN_CAPTURES - captureCount;
    const progress = Math.min((captureCount / MIN_CAPTURES) * 100, 100);
    if (remaining > 0) {
        captureInfo.innerHTML = `
            <i class="fas fa-info-circle"></i> Captures remaining: ${remaining}
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%; background: #667eea;"></div>
            </div>
        `;
        captureBtn.innerHTML = `<i class="fas fa-camera"></i> Capture Photo (${captureCount + 1}/20)`;
        captureBtn.disabled = false;
        submitBtn.disabled = true;
    } else {
        captureInfo.innerHTML = `
            <i class="fas fa-check-circle" style="color: #4CAF50;"></i> Minimum ${MIN_CAPTURES} images captured! (${captureCount} total)
            <div class="progress-bar">
                <div class="progress-fill" style="width: 100%; background: #4CAF50;"></div>
            </div>
        `;
        captureBtn.innerHTML = `<i class="fas fa-camera"></i> Capture More (${captureCount + 1})`;
        captureBtn.disabled = false;
        submitBtn.disabled = false;
    }
}

function initializeFileUpload() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput) return;
    fileInput.addEventListener('change', handleFileSelection);
}

function handleFileSelection(e) {
    const files = Array.from(e.target.files);
    const validFiles = files.filter(file => file.type.startsWith('image/'));
    if (validFiles.length !== files.length) {
        alert('Some files were skipped because they are not images.');
    }
    selectedFiles.push(...validFiles);
    renderUploadPreview();
    e.target.value = '';
}

function addFilesAtIndex(files, index) {
    const validFiles = files.filter(file => file.type.startsWith('image/'));
    selectedFiles.splice(index, 0, ...validFiles);
    renderUploadPreview();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderUploadPreview();
}

function insertFileAtIndex(index) {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = 'image/*';
    input.onchange = function(e) {
        const files = Array.from(e.target.files);
        addFilesAtIndex(files, index);
    };
    input.click();
}

function renderUploadPreview() {
    const uploadPreview = document.getElementById('uploadPreviewContainer');
    const uploadInfo = document.getElementById('uploadInfo');
    const submitBtn = document.getElementById('submitBtn');
    if (!uploadPreview || !uploadInfo) return;
    uploadPreview.innerHTML = '';
    if (selectedFiles.length === 0) {
        uploadInfo.style.display = 'none';
        uploadPreview.style.display = 'none';
        checkUploadSubmitState();
        return;
    }
    uploadInfo.style.display = 'block';
    uploadPreview.style.display = 'block';
    const progress = Math.min((selectedFiles.length / MIN_CAPTURES) * 100, 100);
    if (selectedFiles.length < MIN_CAPTURES) {
        uploadInfo.innerHTML = `
            <i class="fas fa-exclamation-triangle" style="color: #ff9800;"></i> 
            Photos uploaded: <span style="color: #ff9800;">${selectedFiles.length}/20</span> 
            (${MIN_CAPTURES - selectedFiles.length} more needed)
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%; background: #ff9800;"></div>
            </div>
        `;
    } else {
        uploadInfo.innerHTML = `
            <i class="fas fa-check-circle" style="color: #4CAF50;"></i> 
            Minimum ${MIN_CAPTURES} photos uploaded! (${selectedFiles.length} total)
            <div class="progress-bar">
                <div class="progress-fill" style="width: 100%; background: #4CAF50;"></div>
            </div>
        `;
    }
    const previewGrid = document.createElement('div');
    previewGrid.className = 'upload-preview-grid';
    previewGrid.style.cssText = `
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 15px;
        margin-top: 15px;
        padding: 20px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
    `;
    selectedFiles.forEach((file, index) => {
        const container = createImageContainer(file, index);
        previewGrid.appendChild(container);
    });
    const addSlot = createAddSlot();
    previewGrid.appendChild(addSlot);
    uploadPreview.appendChild(previewGrid);
    checkUploadSubmitState();
}

function createImageContainer(file, index) {
    const container = document.createElement('div');
    container.className = 'image-container';
    container.style.cssText = `
        position: relative;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        transition: all 0.3s ease;
        cursor: pointer;
        border: 2px solid rgba(102, 126, 234, 0.2);
    `;
    container.addEventListener('mouseenter', () => {
        container.style.transform = 'translateY(-5px) scale(1.02)';
        container.style.boxShadow = '0 12px 35px rgba(0, 0, 0, 0.2)';
        container.style.borderColor = '#667eea';
    });
    container.addEventListener('mouseleave', () => {
        container.style.transform = 'translateY(0) scale(1)';
        container.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.15)';
        container.style.borderColor = 'rgba(102, 126, 234, 0.2)';
    });
    const reader = new FileReader();
    reader.onload = function(e) {
        container.innerHTML = `
            <img src="${e.target.result}" 
                alt="Preview ${index + 1}" 
                title="${file.name}"
                style="width: 100%; height: 120px; object-fit: cover; display: block;">
            <div class="image-controls" style="
                position: absolute;
                top: 8px;
                right: 8px;
                display: flex;
                gap: 6px;
            ">
                <button type="button" 
                        onclick="removeFile(${index})"
                        title="Remove image"
                        class="control-btn remove-btn"
                        style="
                            width: 28px; height: 28px;
                            border-radius: 50%;
                            border: none;
                            background: linear-gradient(45deg, #ff4757, #ff3742);
                            color: white;
                            font-size: 14px;
                            font-weight: bold;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 4px 12px rgba(255, 71, 87, 0.4);
                            transition: all 0.2s ease;
                        ">
                    ×
                </button>
            </div>
            <div class="image-info" style="
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                background: linear-gradient(transparent, rgba(0,0,0,0.8));
                color: white;
                padding: 8px;
                font-size: 11px;
                text-align: center;
                font-weight: 500;
            ">
                <div style="font-size: 12px; margin-bottom: 2px;">${index + 1} of ${selectedFiles.length}</div>
                <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${file.name}
                </div>
            </div>
        `;
        const img = container.querySelector('img');
        img.addEventListener('click', () => {
            showImageModal(e.target.result, `${index + 1}. ${file.name}`);
        });
    };
    reader.readAsDataURL(file);
    return container;
}

function createAddSlot() {
    const addSlot = document.createElement('div');
    addSlot.className = 'add-slot';
    addSlot.style.cssText = `
        min-height: 120px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 3px dashed #667eea;
        border-radius: 15px;
        cursor: pointer;
        transition: all 0.3s ease;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
        color: #667eea;
        font-weight: 600;
        position: relative;
        overflow: hidden;
    `;
    addSlot.innerHTML = `
        <div style="text-align: center; z-index: 2; position: relative;">
            <i class="fas fa-plus" style="font-size: 28px; margin-bottom: 8px; color: #667eea;"></i>
            <div style="font-size: 14px; margin-bottom: 4px;">Add More Images</div>
        </div>
        <div style="
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(102, 126, 234, 0.1), transparent);
            animation: shine 3s ease-in-out infinite;
            pointer-events: none;
        "></div>
    `;
    addSlot.addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = 'image/*';
        input.onchange = handleFileSelection;
        input.click();
    });
    addSlot.addEventListener('mouseenter', () => {
        addSlot.style.background = 'linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2))';
        addSlot.style.transform = 'translateY(-3px) scale(1.02)';
        addSlot.style.borderColor = '#764ba2';
        addSlot.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.3)';
    });
    addSlot.addEventListener('mouseleave', () => {
        addSlot.style.background = 'linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1))';
        addSlot.style.transform = 'translateY(0) scale(1)';
        addSlot.style.borderColor = '#667eea';
        addSlot.style.boxShadow = 'none';
    });
    return addSlot;
}

function checkUploadSubmitState() {
    const submitBtn = document.getElementById('submitBtn');
    const method = document.querySelector('input[name="photo_method"]:checked')?.value;
    if (method === 'upload') {
        submitBtn.disabled = selectedFiles.length < MIN_CAPTURES;
    }
}

function showImageModal(imageSrc, imageName) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        backdrop-filter: blur(10px);
        animation: modalFadeIn 0.3s ease-out;
    `;
    const modalContent = document.createElement('div');
    modalContent.style.cssText = `
        position: relative;
        max-width: 95%;
        max-height: 95%;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 25px;
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        animation: modalSlideIn 0.3s ease-out;
    `;
    const img = document.createElement('img');
    img.src = imageSrc;
    img.style.cssText = `
        max-width: 100%;
        max-height: 80vh;
        object-fit: contain;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    `;
    const title = document.createElement('h4');
    title.textContent = imageName;
    title.style.cssText = `
        margin: 0 0 20px 0;
        text-align: center;
        color: #2d3748;
        font-weight: 600;
        font-size: 18px;
    `;
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.style.cssText = `
        position: absolute;
        top: 15px;
        right: 15px;
        background: linear-gradient(45deg, #ff4757, #ff3742);
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 15px rgba(255, 71, 87, 0.4);
        transition: all 0.2s ease;
    `;
    closeBtn.onmouseover = () => {
        closeBtn.style.transform = 'scale(1.1)';
        closeBtn.style.boxShadow = '0 6px 20px rgba(255, 71, 87, 0.6)';
    };
    closeBtn.onmouseleave = () => {
        closeBtn.style.transform = 'scale(1)';
        closeBtn.style.boxShadow = '0 4px 15px rgba(255, 71, 87, 0.4)';
    };
    closeBtn.onclick = () => document.body.removeChild(modal);
    modal.onclick = (e) => {
        if (e.target === modal) document.body.removeChild(modal);
    };
    document.body.style.overflow = 'hidden';
    modal.addEventListener('remove', () => {
        document.body.style.overflow = 'auto';
    });
    modalContent.appendChild(title);
    modalContent.appendChild(img);
    modalContent.appendChild(closeBtn);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
}

function addEventListeners() {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', handleFormSubmission);
    }
    window.addEventListener('beforeunload', () => {
        stopCamera();
    });
}

function handleFormSubmission(e) {
    e.preventDefault();
    const method = document.querySelector('input[name="photo_method"]:checked')?.value;
    const form = document.getElementById('registerForm');
    const formData = new FormData(form);
    
    // Add profile picture if selected
    const profilePicInput = document.getElementById('profilePicInput');
    if (profilePicInput.files.length > 0) {
        formData.append('profile_pic', profilePicInput.files[0]);
    }

    if (method === 'upload') {
        if (selectedFiles.length < MIN_CAPTURES) {
            alert(`Please upload at least ${MIN_CAPTURES} photos. Current: ${selectedFiles.length}/${MIN_CAPTURES}`);
            return;
        }
        formData.delete('images');
        selectedFiles.forEach(file => {
            formData.append('images', file);
        });
        fetch('/register', {
            method: 'POST',
            body: formData
        })
        .then(async response => {
            let data;
            try {
                data = await response.json();
            } catch (err) {
                throw new Error("Invalid JSON response from server.");
            }
            if (!response.ok) {
                throw new Error(data.message || "Upload failed.");
            }
            return data;
        })
        .then(data => {
            alert(data.message);
            window.location.href = `/train/${formData.get('generated_id')}`; // Redirect to training page
        })
        .catch(error => {
            console.error('Upload error:', error);
            alert(error.message || "Upload failed.");
        });
    }
    if (method === 'camera') {
        if (captureCount < MIN_CAPTURES) {
            alert(`Please capture at least ${MIN_CAPTURES} photos. Current: ${captureCount}/${MIN_CAPTURES}`);
            return;
        }
        formData.delete('images');
        capturedImages.forEach((blob, index) => {
            formData.append('images', blob, `captured_${index + 1}.jpg`);
        });
        fetch('/register', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                alert(data.message);
                window.location.href = `/train/${formData.get('generated_id')}`; // Redirect to training page
            } else {
                alert(data.message || "An error occurred.");
            }
        })
        .catch(error => {
            console.error('Camera submission error:', error);
            alert("Submission failed.");
        });
    }
}

function updatePreview() {
    const previewContainer = document.getElementById('uploadPreviewContainer');
    if (previewContainer) {
        previewContainer.innerHTML = '';
    }
}

function addRippleEffect() {
    function createRipple(event) {
        const button = event.currentTarget;
        const circle = document.createElement('span');
        const diameter = Math.max(button.clientWidth, button.clientHeight);
        const radius = diameter / 2;
        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${event.clientX - button.offsetLeft - radius}px`;
        circle.style.top = `${event.clientY - button.offsetTop - radius}px`;
        circle.classList.add('ripple');
        const ripple = button.getElementsByClassName('ripple')[0];
        if (ripple) {
            ripple.remove();
        }
        button.appendChild(circle);
    }
    document.querySelectorAll('.btn, button').forEach(button => {
        button.addEventListener('click', createRipple);
    });
    const style = document.createElement('style');
    style.textContent = `
        .btn, button {
            position: relative;
            overflow: hidden;
        }
        .ripple {
            position: absolute;
            border-radius: 50%;
            background-color: rgba(255, 255, 255, 0.6);
            transform: scale(0);
            animation: ripple-animation 0.6s linear;
            pointer-events: none;
        }
        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        @keyframes modalFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes modalSlideIn {
            from { 
                opacity: 0;
                transform: translateY(-50px) scale(0.8);
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        @keyframes shine {
            0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            50% { transform: translateX(100%) translateY(100%) rotate(45deg); }
            100% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
        }
        .control-btn:hover {
            transform: scale(1.1);
            filter: brightness(1.1);
        }
        .control-btn:active {
            transform: scale(0.95);
        }
    `;
    document.head.appendChild(style);
}

function addNavbarScrollEffect() {
    window.addEventListener('scroll', function() {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(255, 255, 255, 0.15)';
                navbar.style.backdropFilter = 'blur(25px)';
            } else {
                navbar.style.background = 'rgba(255, 255, 255, 0.1)';
                navbar.style.backdropFilter = 'blur(20px)';
            }
        }
    });
}

// Replace the existing generateUserID function
function generateUserID() {
    const role = document.getElementById('userRole').value;
    const idInput = document.getElementById('generatedId');
    
    if (!role) {
        idInput.value = '';
        return;
    }

    fetch('/generate_user_id', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ role: role })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            idInput.value = data.user_id;
        } else {
            alert('Error generating user ID: ' + data.message);
            idInput.value = '';
        }
    })
    .catch(error => {
        console.error('Error generating user ID:', error);
        alert('Failed to generate user ID.');
        idInput.value = '';
    });
}

window.togglePhotoMethod = togglePhotoMethod;
window.capturePhoto = capturePhoto;
window.removeFile = removeFile;
window.insertFileAtIndex = insertFileAtIndex;