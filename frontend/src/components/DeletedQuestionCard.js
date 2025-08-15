import API from '../api.js';

export default class DeletedQuestionCard {
    constructor(question) {
        this.question = question;
        this.element = null;
        this.render();
    }

    render() {
        const card = document.createElement('div');
        card.className = 'question-card deleted-card';
        card.dataset.questionId = this.question.id;

        card.innerHTML = `
            <div class="question-header">
                <div class="engine-tag ${this.question.engine}">${this.question.engine.toUpperCase()}</div>
                <div class="question-meta">
                    <span class="status-badge status-deleted">${this.question.status}</span>
                    <span>v${this.question.version}</span>
                    <span>${this.formatDate(this.question.created_at)}</span>
                    ${this.question.deleted_at ? `<span>Deleted: ${this.formatDate(this.question.deleted_at)}</span>` : ''}
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
                    <button class="btn btn-success btn-small restore-btn">
                        Restore
                    </button>
                    <button class="btn btn-danger btn-small remove-btn">
                        Remove Permanently
                    </button>
                </div>
            </div>
        `;

        this.element = card;
        this.attachEventListeners();
    }

    attachEventListeners() {
        const restoreBtn = this.element.querySelector('.restore-btn');
        const removeBtn = this.element.querySelector('.remove-btn');

        restoreBtn.addEventListener('click', () => this.handleRestore());
        removeBtn.addEventListener('click', () => this.handleRemovePermanently());
    }

    async handleRestore() {
        if (!confirm('Are you sure you want to restore this question?')) {
            return;
        }

        try {
            const restoreBtn = this.element.querySelector('.restore-btn');
            restoreBtn.disabled = true;
            restoreBtn.textContent = 'Restoring...';

            const response = await API.undeleteQuestion(this.question.id);
            
            // Update the question data
            this.question = response.question;
            
            // Remove this card from deleted section
            this.element.remove();
            
            // Show success message
            this.showNotification('Question restored successfully!', 'success');
            
            // Trigger event to move question back to in-progress
            this.dispatchEvent('questionRestored', this.question);
            
        } catch (error) {
            console.error('Restore failed:', error);
            this.showNotification(`Restore failed: ${error.message}`, 'error');
        } finally {
            const restoreBtn = this.element.querySelector('.restore-btn');
            restoreBtn.disabled = false;
            restoreBtn.textContent = 'Restore';
        }
    }

    handleRemovePermanently() {
        if (!confirm('Are you sure you want to permanently remove this question? This action cannot be undone.')) {
            return;
        }

        // Remove the card from the DOM (client-side only)
        this.element.remove();
        
        // Show success message
        this.showNotification('Question removed permanently!', 'success');
        
        // Trigger event to update counts
        this.dispatchEvent('questionRemovedPermanently', this.question);
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
