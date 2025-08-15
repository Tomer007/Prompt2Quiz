import API from '../api.js';

export default class ApprovedQuestionCard {
    constructor(question) {
        this.question = question;
        this.element = null;
        this.render();
    }

    render() {
        const card = document.createElement('div');
        card.className = 'question-card approved-card';
        card.dataset.questionId = this.question.id;

        card.innerHTML = `
            <div class="question-header">
                <div class="engine-tag ${this.question.engine}">${this.question.engine.toUpperCase()}</div>
                <div class="question-meta">
                    <span class="status-badge status-approved">${this.question.status}</span>
                    <span>v${this.question.version}</span>
                    <span>${this.formatDate(this.question.created_at)}</span>
                </div>
            </div>

            <div class="question-content">
                <div class="question-text">${this.escapeHtml(this.question.question)}</div>
                
                ${this.question.options ? `
                    <div class="question-options">
                        <strong>Options:</strong>
                        <ul>
                            ${this.question.options.map(option => 
                                `<li>${this.escapeHtml(option)}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                <div class="question-answer">
                    <strong>Answer:</strong> ${this.escapeHtml(this.question.answer)}
                </div>
                
                <div class="question-explanation">
                    <strong>Explanation:</strong> ${this.escapeHtml(this.question.explanation)}
                </div>
                ${this.question.improvement_explanation ? `
                <div class="question-explanation" style="margin-top:6px;">
                    <strong>Improvement notes:</strong> ${this.escapeHtml(this.question.improvement_explanation)}
                </div>` : ''}
            </div>

            <div class="question-actions">
                <div class="action-buttons">
                    <button class="btn btn-secondary btn-small undo-btn">
                        Undo Approval
                    </button>
                    <button class="btn btn-primary btn-small download-btn">
                        Download CSV
                    </button>
                </div>
            </div>
        `;

        this.element = card;
        this.attachEventListeners();
    }

    attachEventListeners() {
        const undoBtn = this.element.querySelector('.undo-btn');
        const downloadBtn = this.element.querySelector('.download-btn');

        undoBtn.addEventListener('click', () => this.handleUndo());
        downloadBtn.addEventListener('click', () => this.handleDownload());
    }

    async handleUndo() {
        if (!confirm('Are you sure you want to undo approval for this question?')) {
            return;
        }

        try {
            const undoBtn = this.element.querySelector('.undo-btn');
            undoBtn.disabled = true;
            undoBtn.textContent = 'Undoing...';

            const response = await API.unapproveQuestion(this.question.id);
            
            // Update the question data
            this.question = response.question;
            
            // Remove this card from approved section
            this.element.remove();
            
            // Show success message
            this.showNotification('Question approval undone successfully!', 'success');
            
            // Trigger event to move question back to in-progress
            this.dispatchEvent('questionUnapproved', this.question);
            
        } catch (error) {
            console.error('Undo approval failed:', error);
            this.showNotification(`Undo approval failed: ${error.message}`, 'error');
        } finally {
            const undoBtn = this.element.querySelector('.undo-btn');
            undoBtn.disabled = false;
            undoBtn.textContent = 'Undo Approval';
        }
    }

    async handleDownload() {
        try {
            const downloadBtn = this.element.querySelector('.download-btn');
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Downloading...';

            // Check if the question can be exported (should always be true for approved questions)
            const canExportResponse = await API.canExportQuestion(this.question.id);
            if (!canExportResponse.can_export) {
                throw new Error('Question cannot be exported - not approved');
            }

            await API.downloadCSV();
            
            this.showNotification('CSV downloaded successfully!', 'success');
            
        } catch (error) {
            console.error('Download failed:', error);
            this.showNotification(`Download failed: ${error.message}`, 'error');
        } finally {
            const downloadBtn = this.element.querySelector('.download-btn');
            downloadBtn.disabled = false;
            downloadBtn.textContent = 'Download CSV';
        }
    }

    dispatchEvent(eventName, data) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }

    showNotification(message, type = 'info') {
        // Create a simple notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            font-weight: 500;
            z-index: 1001;
            background-color: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#007bff'};
        `;
        
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (notification && notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getElement() {
        return this.element;
    }
}
