import API from '../api.js';

export default class QuestionCard {
    constructor(question) {
        this.question = question;
        this.element = null;
        this.render();
    }

    render() {
        const card = document.createElement('div');
        card.className = 'question-card';
        card.dataset.questionId = this.question.id;

        const statusClass = `status-${this.question.status}`;
        const showVersion = !(this.question.status === 'draft' && this.question.version === 1);
        
        const contentDirectionClass = this.getContentDirectionClass();

        card.innerHTML = `
            <div class="question-header">
                <div class="engine-tag ${this.question.engine}">${this.question.engine.toUpperCase()}</div>
                <div class="question-meta">
                    <span class="status-badge ${statusClass}">${this.question.status}</span>
                    ${showVersion ? `<span>v${this.question.version}</span>` : ''}
                    <span>${this.formatDate(this.question.created_at)}</span>
                </div>
            </div>

            <div class="question-content ${contentDirectionClass}">
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
                <textarea 
                    class="tutor-comment" 
                    placeholder="Enter your tutor comment here..."
                    rows="3"
                ></textarea>
                
                <div class="action-buttons">
                    <button class="btn btn-primary btn-small review-btn">
                        Send Comment & Improve
                    </button>
                    <button class="btn btn-success btn-small approve-btn" 
                            ${this.question.status === 'approved' ? 'disabled' : ''}>
                        Approve & Add to CSV
                    </button>
                    <button class="btn btn-danger btn-small delete-btn">
                        Delete
                    </button>
                    <button class="btn btn-info btn-small validate-btn">
                        Validate with AI
                    </button>
                </div>
                
                <!-- Validation Results -->
                <div id="validation-results" class="validation-results" style="display: none;">
                    <!-- Results will be populated here -->
                </div>

                <!-- Change Summary (after Improve) -->
                <div class="change-summary" style="display: none; margin-top: 10px; padding: 10px; border: 1px solid #e0e0e0; border-radius: 6px; background: #fafafa;">
                    <!-- Summary will be populated here -->
                </div>
            </div>
        `;

        this.element = card;
        this.attachEventListeners();
    }

    getContentDirectionClass() {
        const languageValue = (this.question.language || '').toString().toLowerCase();
        const containsHebrew = /[\u0590-\u05FF]/.test(this.question.question || '');
        const isRtl = languageValue.includes('hebrew') || containsHebrew;
        return isRtl ? 'rtl' : 'ltr';
    }

    attachEventListeners() {
        const reviewBtn = this.element.querySelector('.review-btn');
        const approveBtn = this.element.querySelector('.approve-btn');
        const deleteBtn = this.element.querySelector('.delete-btn');
        const validateBtn = this.element.querySelector('.validate-btn');
        const commentTextarea = this.element.querySelector('.tutor-comment');

        reviewBtn.addEventListener('click', () => this.handleReview(commentTextarea));
        approveBtn.addEventListener('click', () => this.handleApprove());
        deleteBtn.addEventListener('click', () => this.handleDelete());
        validateBtn.addEventListener('click', () => this.handleValidate());
    }

    async handleReview(commentTextarea) {
        const comment = (commentTextarea.value || '').trim();
        const reviewBtn = this.element.querySelector('.review-btn');

        try {
            reviewBtn.disabled = true;
            reviewBtn.textContent = 'Improving...';

            const response = await API.improveQuestion(this.question.id, comment);
            
            // Update the question data
            this.question = response.question;
            
            // Build and show a concise change summary
            this.showChangeSummary({
                questionBefore: this.question.question,
                questionAfter: response.question.question,
                answerBefore: this.question.answer,
                answerAfter: response.question.answer,
                explanationBefore: this.question.explanation,
                explanationAfter: response.question.explanation,
                commentUsed: comment,
            });

            // Replace the card with the updated version (refresh UI)
            const newCard = new QuestionCard(response.question);
            this.element.parentNode.replaceChild(newCard.element, this.element);
            
            // Clear the comment
            commentTextarea.value = '';
            
            // Show success message
            this.showNotification('Question improved successfully!', 'success');
            
        } catch (error) {
            console.error('Review failed:', error);
            this.showNotification(`Review failed: ${error.message}`, 'error');
        } finally {
            reviewBtn.disabled = false;
            reviewBtn.textContent = 'Send Comment & Improve';
        }
    }

    async handleApprove() {
        try {
            const approveBtn = this.element.querySelector('.approve-btn');
            approveBtn.disabled = true;
            approveBtn.textContent = 'Approving...';

            // First approve the question
            const approveResponse = await API.approveQuestion(this.question.id);
            this.question = approveResponse.question;

            // Check if the question can be exported
            const canExportResponse = await API.canExportQuestion(this.question.id);
            if (!canExportResponse.can_export) {
                throw new Error('Question cannot be exported - not approved');
            }

            // Then export to CSV
            const exportResponse = await API.exportQuestion(this.question.id);
            
            // Update the card to show approved status
            this.updateCardStatus();
            
            // Dispatch event for question approval
            this.dispatchEvent('questionApproved', this.question);
            
            this.showNotification('Question approved and added to CSV!', 'success');
            
        } catch (error) {
            console.error('Approval failed:', error);
            this.showNotification(`Approval failed: ${error.message}`, 'error');
        } finally {
            const approveBtn = this.element.querySelector('.approve-btn');
            approveBtn.disabled = false;
            approveBtn.textContent = 'Approved ✓';
        }
    }

    async handleDelete() {
        if (!confirm('Are you sure you want to delete this question?')) {
            return;
        }

        try {
            const deleteBtn = this.element.querySelector('.delete-btn');
            deleteBtn.disabled = true;
            deleteBtn.textContent = 'Deleting...';

            await API.deleteQuestion(this.question.id);
            
            // Remove the card from the DOM
            this.element.remove();
            
            // Dispatch event for question deletion
            this.dispatchEvent('questionDeleted', this.question);
            
            this.showNotification('Question deleted successfully!', 'success');
            
        } catch (error) {
            console.error('Delete failed:', error);
            this.showNotification(`Delete failed: ${error.message}`, 'error');
            
            const deleteBtn = this.element.querySelector('.delete-btn');
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'Delete';
        }
    }

    async handleValidate() {
        try {
            const validateBtn = this.element.querySelector('.validate-btn');
            validateBtn.disabled = true;
            validateBtn.textContent = 'Validating...';

            // Prepare question data for verification
            const questionData = {
                id: this.question.id,
                engine: this.question.engine,
                exam_name: this.question.exam_name,
                language: this.question.language,
                question_type: this.question.question_type,
                difficulty: this.question.difficulty,
                question: this.question.question,
                options: this.question.options,
                answer: this.question.answer,
                explanation: this.question.explanation
            };

            const response = await API.verifyQuestion(questionData);
            
            // Display validation results
            this.displayValidationResults(response);
            
            this.showNotification('Question validated successfully!', 'success');
            
        } catch (error) {
            console.error('Validation failed:', error);
            this.showNotification(`Validation failed: ${error.message}`, 'error');
        } finally {
            const validateBtn = this.element.querySelector('.validate-btn');
            validateBtn.disabled = false;
            validateBtn.textContent = 'Validate with AI';
        }
    }

    displayValidationResults(results) {
        const validationResults = this.element.querySelector('#validation-results');
        
        if (!validationResults) return;
        
        const { model_votes = {}, aggregate, proposed_fix_hint } = results;
        const verdictRaw = (aggregate.final_verdict || '').toLowerCase();
        const verdictLabel = verdictRaw === 'approve'
            ? 'Approved'
            : verdictRaw === 'needs_revision'
                ? 'Needs revision'
                : verdictRaw === 'reject'
                    ? 'Rejected'
                    : aggregate.final_verdict;
        
        // Build per-engine votes rows
        const formatConfidence = (c) => {
            if (typeof c !== 'number') return '';
            // If provider returns 0..1 show %, otherwise show as fixed
            return c <= 1 ? `${Math.round(c * 100)}%` : c.toFixed(1);
        };
        const formatVerdict = (v) => {
            const vr = (v || '').toLowerCase();
            if (vr === 'approve') return 'Approved';
            if (vr === 'needs_revision') return 'Needs revision';
            if (vr === 'reject') return 'Rejected';
            return v || '';
        };
        const votesRows = Object.entries(model_votes).map(([engine, vote]) => `
            <tr>
                <td class="engine-cell">${engine.toUpperCase()}</td>
                <td>${(vote.score ?? '').toString()}</td>
                <td>${formatVerdict(vote.verdict)}</td>
                <td>${formatConfidence(vote.confidence)}</td>
                <td>${(vote.issues || []).join(', ')}</td>
            </tr>
        `).join('');
        
        // Create the results HTML
        const resultsHTML = `
            ${votesRows ? `
            <div class="validation-votes">
                <div style="font-weight:600; margin-bottom:6px;">Per-engine results</div>
                <table class="votes-table">
                    <thead>
                        <tr>
                            <th>Engine</th>
                            <th>Score</th>
                            <th>Status</th>
                            <th>Confidence</th>
                            <th>Issues</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${votesRows}
                    </tbody>
                </table>
            </div>` : ''}
            <div class="validation-summary">
                <div class="validation-row">
                    <span class="validation-label">Mean score:</span>
                    <span class="validation-value">${aggregate.mean_score}</span>
                </div>
                <div class="validation-row">
                    <span class="validation-label">Solver agreement:</span>
                    <span class="validation-value">${aggregate.solver_agreement ? 'Yes' : 'No'}</span>
                </div>
                <div class="validation-row">
                    <span class="validation-label">Decision:</span>
                    <span class="validation-value verdict-${verdictRaw}">${verdictLabel}</span>
                </div>
                ${aggregate.combined_issues.length > 0 ? `
                    <div class="validation-row">
                        <span class="validation-label">Issues:</span>
                        <span class="validation-value">${aggregate.combined_issues.join(', ')}</span>
                    </div>
                ` : ''}
                ${proposed_fix_hint ? `
                    <div class="validation-row">
                        <span class="validation-label">Fix hint:</span>
                        <span class="validation-value">${proposed_fix_hint}</span>
                    </div>
                ` : ''}
            </div>
        `;
        
        validationResults.innerHTML = resultsHTML;
        validationResults.style.display = 'block';
    }

    showChangeSummary({ questionBefore, questionAfter, answerBefore, answerAfter, explanationBefore, explanationAfter, commentUsed }) {
        const container = this.element.querySelector('.change-summary');
        if (!container) return;

        const changed = [];
        if (questionBefore !== questionAfter) changed.push('Question text');
        if (answerBefore !== answerAfter) changed.push('Answer');
        if (explanationBefore !== explanationAfter) changed.push('Explanation');

        const summaryHTML = `
            <div style="font-weight:600; margin-bottom:6px;">Change summary</div>
            ${commentUsed ? `<div style="margin-bottom:8px;"><span style="font-weight:600;">Tutor comment:</span> ${this.escapeHtml(commentUsed)}</div>` : ''}
            ${changed.length === 0 ? '<div>No substantive changes were applied.</div>' : ''}
            ${questionBefore !== questionAfter ? `
                <div style="margin-top:6px;">
                    <div style="font-weight:600;">Question</div>
                    <div><span style="opacity:0.7;">Before:</span> ${this.escapeHtml(questionBefore)}</div>
                    <div><span style="opacity:0.7;">After:</span> ${this.escapeHtml(questionAfter)}</div>
                </div>` : ''}
            ${answerBefore !== answerAfter ? `
                <div style="margin-top:6px;">
                    <div style="font-weight:600;">Answer</div>
                    <div><span style="opacity:0.7;">Before:</span> ${this.escapeHtml(answerBefore)}</div>
                    <div><span style="opacity:0.7;">After:</span> ${this.escapeHtml(answerAfter)}</div>
                </div>` : ''}
            ${explanationBefore !== explanationAfter ? `
                <div style="margin-top:6px;">
                    <div style="font-weight:600;">Explanation</div>
                    <div><span style="opacity:0.7;">Before:</span> ${this.escapeHtml(explanationBefore)}</div>
                    <div><span style="opacity:0.7;">After:</span> ${this.escapeHtml(explanationAfter)}</div>
                </div>` : ''}
        `;

        container.innerHTML = summaryHTML;
        container.style.display = 'block';
    }

    updateCardStatus() {
        const statusBadge = this.element.querySelector('.status-badge');
        const approveBtn = this.element.querySelector('.approve-btn');
        
        statusBadge.className = `status-badge status-${this.question.status}`;
        statusBadge.textContent = this.question.status;
        
        if (this.question.status === 'approved') {
            approveBtn.disabled = true;
            approveBtn.textContent = 'Approved ✓';
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
