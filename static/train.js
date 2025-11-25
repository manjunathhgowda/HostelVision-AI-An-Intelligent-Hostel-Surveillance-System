document.addEventListener('DOMContentLoaded', function() {
    const trainBtn = document.getElementById('trainBtn');
    const trainStatus = document.getElementById('trainStatus');

    if (trainBtn) {
        trainBtn.addEventListener('click', function() {
            const userId = trainBtn.getAttribute('data-user-id');
            trainBtn.disabled = true;
            trainStatus.innerHTML = '<span class="text-info">Training in progress...</span>';

            fetch(`/train_model/${userId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                trainBtn.disabled = false;
                if (data.status === 'success') {
                    trainStatus.innerHTML = '<span class="text-success">' + data.message + '</span>';
                } else {
                    trainStatus.innerHTML = '<span class="text-danger">' + (data.message || 'Training failed.') + '</span>';
                }
            })
            .catch(error => {
                trainBtn.disabled = false;
                trainStatus.innerHTML = '<span class="text-danger">Error: ' + error.message + '</span>';
                console.error('Training error:', error);
            });
        });
    }
});