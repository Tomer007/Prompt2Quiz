import API from './api.js';
import QuestionCard from './components/QuestionCard.js';
import ApprovedQuestionCard from './components/ApprovedQuestionCard.js';
import DeletedQuestionCard from './components/DeletedQuestionCard.js';

export default class App {
    constructor() {
        this.inProgressQuestions = [];
        this.approvedQuestions = [];
        this.deletedQuestions = [];
        this.currentTab = 'in-progress';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadExistingQuestions();
    }

    bindEvents() {
        const generateForm = document.getElementById('generateForm');
        const downloadCsvBtn = document.getElementById('downloadCsvBtn');
        const tabBtns = document.querySelectorAll('.tab-btn');

        generateForm.addEventListener('submit', (e) => this.handleGenerateSubmit(e));
        downloadCsvBtn.addEventListener('click', () => this.handleDownloadCSV());
        
        // Tab switching
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        // Listen for question approval events
        document.addEventListener('questionApproved', (e) => this.handleQuestionApproved(e.detail));
        document.addEventListener('questionUnapproved', (e) => this.handleQuestionUnapproved(e.detail));
        document.addEventListener('questionDeleted', (e) => this.handleQuestionDeleted(e.detail));
        document.addEventListener('questionRestored', (e) => this.handleQuestionRestored(e.detail));
        document.addEventListener('questionRemovedPermanently', (e) => this.handleQuestionRemovedPermanently(e.detail));
    }

    async loadExistingQuestions() {
        try {
            // Load in-progress questions
            const inProgressResponse = await API.getQuestions('in_progress');
            this.inProgressQuestions = inProgressResponse.questions || [];
            
            // Load approved questions
            const approvedResponse = await API.getQuestions('approved');
            this.approvedQuestions = approvedResponse.questions || [];
            
            // Load deleted questions
            const deletedResponse = await API.getQuestions('deleted');
            this.deletedQuestions = deletedResponse.questions || [];
            
            this.renderQuestions();
            this.updateTabCounts();
        } catch (error) {
            console.error('Failed to load existing questions:', error);
        }
    }

    async switchTab(tabName) {
        // Map tab names to container IDs
        const containerIdByTab = {
            'in-progress': 'inProgressContainer',
            'approved': 'approvedContainer',
            'deleted': 'deletedContainer',
        };

        const targetContainerId = containerIdByTab[tabName] || 'inProgressContainer';

        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === targetContainerId);
        });

        this.currentTab = tabName;

        // Ensure the visible tab content is freshly rendered
        if (tabName === 'in-progress') {
            try {
                const inProgressResponse = await API.getQuestions('in_progress');
                this.inProgressQuestions = inProgressResponse.questions || [];
            } catch (err) {
                console.error('Failed to refresh in-progress questions:', err);
            }
            this.renderInProgressQuestions();
            this.updateTabCounts();
        } else if (tabName === 'approved') {
            try {
                const approvedResponse = await API.getQuestions('approved');
                this.approvedQuestions = approvedResponse.questions || [];
            } catch (err) {
                console.error('Failed to refresh approved questions:', err);
            }
            this.renderApprovedQuestions();
            this.updateTabCounts();
        } else if (tabName === 'deleted') {
            try {
                const deletedResponse = await API.getQuestions('deleted');
                this.deletedQuestions = deletedResponse.questions || [];
            } catch (err) {
                console.error('Failed to refresh deleted questions:', err);
            }
            this.renderDeletedQuestions();
            this.updateTabCounts();
        } else {
            this.renderQuestions();
        }
    }

    async handleGenerateSubmit(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const data = {
            exam_name: formData.get('examName'),
            language: formData.get('language'),
            question_type: formData.get('questionType'),
            difficulty: parseInt(formData.get('difficulty')),
            notes: formData.get('notes'),
            num_questions: parseInt(formData.get('numQuestions')),
            engines: formData.getAll('engines')
        };

        // Validate form data
        if (!this.validateFormData(data)) {
            return;
        }

        try {
            this.showLoading(true);
            this.disableGenerateButton(true);

            const response = await API.generateQuestions(data);
            
            // Add new questions to in-progress list
            this.inProgressQuestions.push(...response.questions);
            
            // Render the new questions
            this.renderQuestions();
            this.updateTabCounts();
            
            // Show success message
            this.showNotification(`Successfully generated ${response.questions.length} questions!`, 'success');
            
            // Reset form
            event.target.reset();
            
        } catch (error) {
            console.error('Generation failed:', error);
            this.showNotification(`Generation failed: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
            this.disableGenerateButton(false);
        }
    }

    validateFormData(data) {
        if (!data.exam_name.trim()) {
            this.showNotification('Exam name is required', 'error');
            return false;
        }
        
        if (!data.language.trim()) {
            this.showNotification('Language is required', 'error');
            return false;
        }
        
        if (!data.question_type.trim()) {
            this.showNotification('Question type is required', 'error');
            return false;
        }
        
        if (data.difficulty < 1 || data.difficulty > 10) {
            this.showNotification('Difficulty must be between 1 and 10', 'error');
            return false;
        }
        
        if (data.num_questions < 1 || data.num_questions > 50) {
            this.showNotification('Number of questions must be between 1 and 50', 'error');
            return false;
        }
        
        if (data.engines.length === 0) {
            this.showNotification('Please select at least one AI engine', 'error');
            return false;
        }
        
        return true;
    }

    renderQuestions() {
        this.renderInProgressQuestions();
        this.renderApprovedQuestions();
        this.renderDeletedQuestions();
    }

    renderInProgressQuestions() {
        const container = document.querySelector('#inProgressContainer .questions-container');
        
        if (this.inProgressQuestions.length === 0) {
            container.innerHTML = '<p class="no-questions">No questions in progress. Use the form above to get started.</p>';
            return;
        }
        
        // Clear container
        container.innerHTML = '';
        
        // Render each in-progress question
        this.inProgressQuestions.forEach(question => {
            const questionCard = new QuestionCard(question);
            container.appendChild(questionCard.getElement());
        });
    }

    renderApprovedQuestions() {
        const container = document.querySelector('#approvedContainer .questions-container');
        
        if (this.approvedQuestions.length === 0) {
            container.innerHTML = '<p class="no-questions">No approved questions yet.</p>';
            return;
        }
        
        // Clear container
        container.innerHTML = '';
        
        // Render each approved question
        this.approvedQuestions.forEach(question => {
            const approvedCard = new ApprovedQuestionCard(question);
            container.appendChild(approvedCard.getElement());
        });
    }

    renderDeletedQuestions() {
        const container = document.querySelector('#deletedContainer .questions-container');
        
        if (this.deletedQuestions.length === 0) {
            container.innerHTML = '<p class="no-questions">No deleted questions yet.</p>';
            return;
        }
        
        // Clear container
        container.innerHTML = '';
        
        // Render each deleted question
        this.deletedQuestions.forEach(question => {
            const deletedCard = new DeletedQuestionCard(question);
            container.appendChild(deletedCard.getElement());
        });
    }

    updateTabCounts() {
        const inProgressCount = document.getElementById('inProgressCount');
        const approvedCount = document.getElementById('approvedCount');
        const deletedCount = document.getElementById('deletedCount');
        
        inProgressCount.textContent = this.inProgressQuestions.length;
        approvedCount.textContent = this.approvedQuestions.length;
        deletedCount.textContent = this.deletedQuestions.length;
    }

    handleQuestionApproved(question) {
        // Remove from in-progress list
        this.inProgressQuestions = this.inProgressQuestions.filter(q => q.id !== question.id);
        
        // Add to approved list
        this.approvedQuestions.unshift(question); // Add to beginning
        
        // Re-render both sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question approved and added to CSV!', 'success');
    }

    handleQuestionUnapproved(question) {
        // Remove from approved list
        this.approvedQuestions = this.approvedQuestions.filter(q => q.id !== question.id);
        
        // Add back to in-progress list
        this.inProgressQuestions.unshift(question); // Add to beginning
        
        // Re-render both sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question approval undone successfully!', 'success');
    }

    handleQuestionDeleted(question) {
        // Remove from in-progress list
        this.inProgressQuestions = this.inProgressQuestions.filter(q => q.id !== question.id);
        
        // Add to deleted list
        this.deletedQuestions.unshift(question); // Add to beginning
        
        // Re-render all sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question deleted successfully!', 'success');
    }

    handleQuestionRestored(question) {
        // Remove from deleted list
        this.deletedQuestions = this.deletedQuestions.filter(q => q.id !== question.id);
        
        // Add back to in-progress list
        this.inProgressQuestions.unshift(question); // Add to beginning
        
        // Re-render all sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question restored successfully!', 'success');
    }

    handleQuestionRemovedPermanently(question) {
        // Remove from deleted list (client-side only)
        this.deletedQuestions = this.deletedQuestions.filter(q => q.id !== question.id);
        
        // Re-render all sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question removed permanently!', 'success');
    }

    async handleDownloadCSV() {
        try {
            const downloadBtn = document.getElementById('downloadCsvBtn');
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Downloading...';
            
            await API.downloadCSV();
            
            this.showNotification('CSV downloaded successfully!', 'success');
            
        } catch (error) {
            console.error('CSV download failed:', error);
            this.showNotification(`CSV download failed: ${error.message}`, 'error');
        } finally {
            const downloadBtn = document.getElementById('downloadCsvBtn');
            downloadBtn.disabled = false;
            downloadBtn.textContent = 'Download CSV';
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }

    disableGenerateButton(disable) {
        const generateBtn = document.getElementById('generateBtn');
        generateBtn.disabled = disable;
        generateBtn.textContent = disable ? 'Generating...' : 'Generate Questions';
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
}
