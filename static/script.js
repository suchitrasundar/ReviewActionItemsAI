let currentDocumentId = null;

function uploadDocument(type) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*,application/pdf,.doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    fileInput.onchange = function(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function(e) {
            const base64 = e.target.result.split(',')[1];
            fetch('/upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document: base64,
                    document_type: type === 'citizenship' ? 'Proof of Citizenship' : 'Student W2',
                    student_id: 'student123',
                    file_name: file.name
                }),
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw err; });
                }
                return response.json();
            })
            .then(data => {
                console.log('Success:', data);
                const label = document.getElementById(type + 'Label');
                label.innerHTML += ` <span class="success-mark">✔</span> (Score: ${data.score})`;
                fetchActionItems();
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('Upload failed: ' + (error.error || 'Unknown error'));
            });
        };
        reader.readAsDataURL(file);
    };
    fileInput.click();
}

function fetchActionItems() {
    fetch('/action-items')
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            const actionItemsContainer = document.getElementById('action-items');
            actionItemsContainer.innerHTML = '';
            data.forEach(item => {
                const div = document.createElement('div');
                div.className = 'action-item';
                div.innerHTML = `
                    <span>${item.document_type} (Score: ${item.score})</span>
                    <button onclick="openReviewModal('${item.document_id}', '${item.document_type}', ${item.score})">Review</button>
                `;
                actionItemsContainer.appendChild(div);
            });
        })
        .catch((error) => {
            console.error('Error fetching action items:', error);
            alert('Failed to fetch action items: ' + (error.error || 'Unknown error'));
        });
}

function openReviewModal(documentId, documentType, score) {
    currentDocumentId = documentId;
    const modal = document.getElementById('reviewModal');
    const reviewTitle = document.getElementById('reviewTitle');
    const scoreText = document.getElementById('scoreText');
    const documentPreview = document.getElementById('documentPreview');
    const pdfViewer = document.getElementById('pdfViewer');
    const docxViewer = document.getElementById('docxViewer');

    reviewTitle.textContent = `Reviewing document: ${documentType}`;
    scoreText.textContent = `Score: ${score}`;

    // Reset viewers
    documentPreview.style.display = 'none';
    pdfViewer.style.display = 'none';
    docxViewer.innerHTML = '';

    fetch(`/document/${documentId}`)
        .then(response => {
            const contentType = response.headers.get('Content-Type');
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'unknown';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            return response.blob().then(blob => ({ blob, contentType, filename }));
        })
        .then(({ blob, contentType, filename }) => {
            const fileExtension = filename.split('.').pop().toLowerCase();

            if (contentType === 'application/pdf' || fileExtension === 'pdf') {
                previewPDF(blob);
            } else if (contentType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' || 
                       contentType === 'application/msword' ||
                       fileExtension === 'docx' || fileExtension === 'doc') {
                previewDOCX(blob);
            } else {
                previewImage(blob);
            }

            modal.style.display = 'block';
        })
        .catch((error) => {
            console.error('Error:', error);
            alert('Error loading document preview');
        });
}

function previewPDF(blob) {
    const pdfViewer = document.getElementById('pdfViewer');
    pdfViewer.style.display = 'block';

    const url = URL.createObjectURL(blob);
    pdfjsLib.getDocument(url).promise.then(pdf => {
        pdf.getPage(1).then(page => {
            const scale = 1.5;
            const viewport = page.getViewport({ scale: scale });

            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            page.render(renderContext);

            pdfViewer.innerHTML = '';
            pdfViewer.appendChild(canvas);
        });
    });
}

function previewDOCX(blob) {
    const docxViewer = document.getElementById('docxViewer');
    docxViewer.innerHTML = 'Loading Word document preview...';
    docxViewer.style.display = 'block';

    const reader = new FileReader();
    reader.onload = function(e) {
        const arrayBuffer = e.target.result;
        
        mammoth.convertToHtml({arrayBuffer: arrayBuffer})
            .then(function(result){
                const html = result.value;
                docxViewer.innerHTML = html;
                
                // Apply some basic styling to the preview
                const style = document.createElement('style');
                style.textContent = `
                    #docxViewer {
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        padding: 20px;
                        max-height: 400px;
                        overflow-y: auto;
                    }
                    #docxViewer img {
                        max-width: 100%;
                        height: auto;
                    }
                `;
                docxViewer.prepend(style);
            })
            .catch(function(error){
                console.error(error);
                docxViewer.innerHTML = 'Error previewing Word document: ' + error.message;
            });
    };
    reader.readAsArrayBuffer(blob);
}

function previewImage(blob) {
    const documentPreview = document.getElementById('documentPreview');
    documentPreview.style.display = 'block';
    documentPreview.src = URL.createObjectURL(blob);
}

function reviewDocument(status) {
    fetch('/review', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            document_id: currentDocumentId,
            status: status
        }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        closeModal();
        fetchActionItems();
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

function closeModal() {
    const modal = document.getElementById('reviewModal');
    modal.style.display = 'none';
}

document.querySelector('.close').onclick = closeModal;

window.onclick = function(event) {
    const modal = document.getElementById('reviewModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

fetchActionItems();
