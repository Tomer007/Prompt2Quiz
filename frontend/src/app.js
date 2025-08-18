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
        this.lastEvaluations = null;
        this.lastWinnerId = null;
        this.lastCandidates = null; // [{id, engine}] from latest selection round
        this.lastRequest = null; // user input used for the last selection round
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadExistingQuestions();
    }

    getQuestionTimestamp(question) {
        try {
            // Prefer created_at; fallback to deleted_at for deleted list, else 0
            const primary = question && question.created_at ? new Date(question.created_at).getTime() : 0;
            const secondary = question && question.deleted_at ? new Date(question.deleted_at).getTime() : 0;
            return Math.max(primary, secondary);
        } catch (_) {
            return 0;
        }
    }

    sortNewestFirst(list) {
        return (list || []).slice().sort((a, b) => this.getQuestionTimestamp(b) - this.getQuestionTimestamp(a));
    }

    bindEvents() {
        const generateForm = document.getElementById('generateForm');
        const downloadCsvBtn = document.getElementById('downloadCsvBtn');
        const tabBtns = document.querySelectorAll('.tab-btn');

        generateForm.addEventListener('submit', (e) => this.handleGenerateSubmit(e));
        downloadCsvBtn.addEventListener('click', () => this.handleDownloadCSV());
        // No hide button; panel is always visible when data exists
        
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
            this.inProgressQuestions = this.sortNewestFirst(inProgressResponse.questions);
            
            // Load approved questions
            const approvedResponse = await API.getQuestions('approved');
            this.approvedQuestions = this.sortNewestFirst(approvedResponse.questions);
            
            // Load deleted questions
            const deletedResponse = await API.getQuestions('deleted');
            this.deletedQuestions = this.sortNewestFirst(deletedResponse.questions);
            
            // Restore last selection round from storage BEFORE first render
            this.loadSelectionRoundFromStorage();

            // Now render with selection-round context available
            this.renderQuestions();
            this.updateTabCounts();
            this.renderTournamentResults(this.lastCandidates || this.inProgressQuestions);
            this.highlightTournamentWinner();
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
                this.inProgressQuestions = this.sortNewestFirst(inProgressResponse.questions);
            } catch (err) {
                console.error('Failed to refresh in-progress questions:', err);
            }
            this.renderInProgressQuestions();
            this.updateTabCounts();
        } else if (tabName === 'approved') {
            try {
                const approvedResponse = await API.getQuestions('approved');
                this.approvedQuestions = this.sortNewestFirst(approvedResponse.questions);
            } catch (err) {
                console.error('Failed to refresh approved questions:', err);
            }
            this.renderApprovedQuestions();
            this.updateTabCounts();
        } else if (tabName === 'deleted') {
            try {
                const deletedResponse = await API.getQuestions('deleted');
                this.deletedQuestions = this.sortNewestFirst(deletedResponse.questions);
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
            
            // Add new questions and keep newest first
            this.inProgressQuestions = this.sortNewestFirst([
                ...response.questions,
                ...this.inProgressQuestions,
            ]);
            
            // Render the new questions
            this.renderQuestions();
            this.updateTabCounts();
            // Store and render tournament results
            this.lastEvaluations = response.evaluations || null;
            this.lastWinnerId = response.winner_id || null;
            this.lastCandidates = (response.questions || []).map(q => ({ id: q.id, engine: q.engine }));
            this.lastRequest = data;
            this.saveSelectionRoundToStorage();
            this.renderTournamentResults(this.lastCandidates);
            this.highlightTournamentWinner();
            
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
        
        // If selection round results exist, don't render duplicate question cards below
        if (this.lastEvaluations && Object.keys(this.lastEvaluations).length > 0) {
            container.innerHTML = '';
            return;
        }

        if (this.inProgressQuestions.length === 0) {
            container.innerHTML = '<p class="no-questions">No questions in progress. Use the form above to get started.</p>';
            return;
        }
        
        // Clear container
        container.innerHTML = '';

        // Fallback: render all in-progress questions (no selection round context)
        this.inProgressQuestions.forEach(question => {
            const questionCard = new QuestionCard(question);
            container.appendChild(questionCard.getElement());
        });

        // Re-apply winner highlight if exists
        this.highlightTournamentWinner();

        // Re-render tournament results panel if we still have the last results
        if (this.lastEvaluations) {
            this.renderTournamentResults(this.inProgressQuestions);
        }
    }

    renderTournamentResults(latestQuestions) {
        try {
            const container = document.getElementById('tournamentContainer');
            const host = document.getElementById('tournamentResults');
            if (!container || !host) return;
            
            const evaluations = this.lastEvaluations;
            if (!evaluations || Object.keys(evaluations).length === 0) {
                container.classList.add('is-empty');
                host.innerHTML = '<div class="tournament-empty">No selection round results yet. Generate to see rankings.</div>';
                return;
            } else {
                container.classList.remove('is-empty');
            }
            
            // Build ordered candidate list (winner first), with full question objects
            const byId = {};
            (this.inProgressQuestions || []).forEach(q => { if (q && q.id) byId[q.id] = q; });
            const winnerId = this.lastWinnerId;
            const candidateIds = Object.keys(evaluations);
            const orderedIds = [
                ...candidateIds.filter(id => id === winnerId),
                ...candidateIds.filter(id => id !== winnerId)
            ];
            const candidates = orderedIds.map(id => byId[id]).filter(Boolean);

            // Build tabs UI (candidate tabs + Stats tab)
            const tabsId = 'sr-tabs';
            const tabBtnsHtml = candidates.map((q, idx) => {
                const engine = (q.engine || '').toString().toUpperCase();
                return `<button class="mini-tab-btn ${idx === 0 ? 'active' : ''}" data-tab="${tabsId}-${idx}"><span class="engine-pill ${q.engine}">${engine}</span></button>`;
            }).join('') + `<button class="mini-tab-btn" data-tab="${tabsId}-stats"><span class="mini-tab-label">STATS</span></button>` + `<button class="mini-tab-btn" data-tab="${tabsId}-query"><span class="mini-tab-label">QUERY</span></button>`;
            const tabContentsHtml = candidates.map((q, idx) => `
                <div id="${tabsId}-${idx}" class="mini-tab-content ${idx === 0 ? 'active' : ''}"></div>
            `).join('') + `
                <div id="${tabsId}-stats" class="mini-tab-content"></div>
                <div id="${tabsId}-query" class="mini-tab-content"></div>
            `;

            host.innerHTML = `
                <div class="mini-tabs">
                    <div class="mini-tab-buttons">${tabBtnsHtml}</div>
                    <div class="mini-tab-contents">${tabContentsHtml}</div>
                </div>
            `;

            // Mount QuestionCard in each tab content
            candidates.forEach((q, idx) => {
                const mount = host.querySelector(`#${tabsId}-${idx}`);
                if (!mount) return;
                const card = new QuestionCard(q);
                mount.appendChild(card.getElement());
            });

            // Wire tab switching
            const btns = Array.from(host.querySelectorAll('.mini-tab-btn'));
            const contents = Array.from(host.querySelectorAll('.mini-tab-content'));
            btns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const target = btn.getAttribute('data-tab');
                    btns.forEach(b => b.classList.toggle('active', b === btn));
                    contents.forEach(c => c.classList.toggle('active', c.id === target));
                });
            });

            // Render evaluations stats inside stats tab
            try {
                const statsMount = host.querySelector(`#${tabsId}-stats`);
                if (statsMount) {
                    // Compute stats rows from evaluations
                    const idToEngine = {};
                    (latestQuestions || []).forEach(q => { if (q && q.id) idToEngine[q.id] = (q.engine || '').toString(); });
                    const candidateIds = Object.keys(evaluations);
                    const rows = candidateIds.map((qid) => {
                        const votes = evaluations[qid] || {};
                        const voteList = Object.values(votes);
                        const totalPoints = voteList.reduce((acc, v) => acc + (Number(v.points) || 0), 0);
                        const scores = voteList.map(v => Number(v.score) || 0);
                        const meanScore = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
                        return {
                            qid,
                            engine: idToEngine[qid] || '',
                            totalPoints,
                            meanScore,
                            votes,
                        };
                    }).sort((a, b) => (b.totalPoints - a.totalPoints) || (b.meanScore - a.meanScore) || a.qid.localeCompare(b.qid));

                    const renderPerEvaluator = (votes) => {
                        return Object.entries(votes || {}).map(([engine, v]) => {
                            const rank = (v && v.rank != null) ? `#${v.rank}` : '';
                            const pts = (v && v.points != null) ? ` (${v.points})` : '';
                            return `<span class="eval-chip">${engine.toUpperCase()}: ${rank}${pts}</span>`;
                        }).join(' ');
                    };

                    const tableRowsHtml = rows.map((r, idx) => {
                        const isWinner = r.qid === this.lastWinnerId;
                        return `
                            <tr class="${isWinner ? 'winner-row' : ''}">
                                <td>${idx + 1}</td>
                                <td><span class="engine-pill ${r.engine}">${(r.engine || '').toString().toUpperCase()}</span></td>
                                <td>${r.totalPoints}</td>
                                <td>${r.meanScore.toFixed(1)}</td>
                                <td>${renderPerEvaluator(evaluations[r.qid])}</td>
                            </tr>
                        `;
                    }).join('');

                    statsMount.innerHTML = `
                        <div class="tournament-table-wrap">
                            <table class="tournament-table" style="width:100%; border-collapse: collapse;">
                                <thead>
                                    <tr>
                                        <th style="text-align:left; padding:6px; border-bottom:1px solid #e5e7eb;">Rank</th>
                                        <th style="text-align:left; padding:6px; border-bottom:1px solid #e5e7eb;">Candidate</th>
                                        <th style="text-align:left; padding:6px; border-bottom:1px solid #e5e7eb;">Points</th>
                                        <th style="text-align:left; padding:6px; border-bottom:1px solid #e5e7eb;">Mean score</th>
                                        <th style="text-align:left; padding:6px; border-bottom:1px solid #e5e7eb;">Per-evaluator</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tableRowsHtml}
                                </tbody>
                            </table>
                        </div>
                    `;
                }
            } catch (_) {
                // ignore stats render errors
            }

            // Render user input query/settings inside query tab
            try {
                const queryMount = host.querySelector(`#${tabsId}-query`);
                if (queryMount) {
                    const req = this.lastRequest || {};
                    const engines = (req.engines || []).map(e => e.toString().toUpperCase()).join(', ');
                    const details = {
                        Exam: req.exam_name,
                        Language: req.language,
                        Type: req.question_type,
                        Difficulty: typeof req.difficulty === 'number' ? req.difficulty : (req.difficulty || ''),
                        Notes: req.notes || '',
                        Engines: engines,
                        Requested: (req.num_questions != null ? req.num_questions : ''),
                    };
                    const rows = Object.entries(details).map(([k, v]) => `
                        <div class="query-row"><span class="query-key">${k}:</span><span class="query-val">${this.escapeHtml ? this.escapeHtml(String(v)) : String(v)}</span></div>
                    `).join('');
                    queryMount.innerHTML = `<div class="query-details">${rows}</div>`;
                }
            } catch (_) {
                // ignore
            }
        } catch (err) {
            console.error('Failed to render tournament results:', err);
        }
    }

    highlightTournamentWinner() {
        try {
            if (!this.lastWinnerId) return;
            const el = document.querySelector(`.question-card[data-question-id="${this.lastWinnerId}"]`);
            if (!el) return;
            el.classList.add('tournament-winner');
            const header = el.querySelector('.question-header');
            const slot = el.querySelector('.winner-slot');
            const existingRibbon = el.querySelector('.winner-ribbon');
            if (existingRibbon) return;

            const ribbon = document.createElement('span');
            ribbon.className = 'winner-ribbon';
            ribbon.setAttribute('title', 'Selection Round Winner');
            ribbon.setAttribute('aria-label', 'Selection Round Winner');
            ribbon.innerHTML = `<span class="ribbon-emoji" aria-hidden="true">🏆</span><span class="ribbon-text">Winner</span>`;

            // Prefer the slot right after engine tag, otherwise insert after engine tag directly
            if (slot) {
                slot.appendChild(ribbon);
            } else {
                const engineTag = el.querySelector('.engine-tag');
                if (engineTag && engineTag.parentNode) {
                    engineTag.insertAdjacentElement('afterend', ribbon);
                } else if (header) {
                    header.insertBefore(ribbon, header.firstChild);
                } else {
                    el.appendChild(ribbon);
                }
            }
        } catch (_) {
            // no-op
        }
    }

    saveSelectionRoundToStorage() {
        try {
            if (this.lastEvaluations) {
                localStorage.setItem('selectionRound.evaluations', JSON.stringify(this.lastEvaluations));
            }
            if (this.lastWinnerId) {
                localStorage.setItem('selectionRound.winnerId', this.lastWinnerId);
            }
            if (this.lastCandidates) {
                localStorage.setItem('selectionRound.candidates', JSON.stringify(this.lastCandidates));
            }
        } catch (_) {
            // ignore storage errors
        }
    }

    loadSelectionRoundFromStorage() {
        try {
            const evalsRaw = localStorage.getItem('selectionRound.evaluations');
            const winnerRaw = localStorage.getItem('selectionRound.winnerId');
            const candidatesRaw = localStorage.getItem('selectionRound.candidates');
            this.lastEvaluations = evalsRaw ? JSON.parse(evalsRaw) : null;
            this.lastWinnerId = winnerRaw || null;
            this.lastCandidates = candidatesRaw ? JSON.parse(candidatesRaw) : null;
        } catch (_) {
            this.lastEvaluations = null;
            this.lastWinnerId = null;
            this.lastCandidates = null;
        }
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
        
        // Add to approved list and keep newest first
        this.approvedQuestions = this.sortNewestFirst([question, ...this.approvedQuestions]);
        
        // Re-render both sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question approved and added to CSV!', 'success');
    }

    handleQuestionUnapproved(question) {
        // Remove from approved list
        this.approvedQuestions = this.approvedQuestions.filter(q => q.id !== question.id);
        
        // Add back to in-progress list and keep newest first
        this.inProgressQuestions = this.sortNewestFirst([question, ...this.inProgressQuestions]);
        
        // Re-render both sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question approval undone successfully!', 'success');
    }

    handleQuestionDeleted(question) {
        // Remove from in-progress list
        this.inProgressQuestions = this.inProgressQuestions.filter(q => q.id !== question.id);
        
        // Add to deleted list and keep newest first
        this.deletedQuestions = this.sortNewestFirst([question, ...this.deletedQuestions]);
        
        // Re-render all sections
        this.renderQuestions();
        this.updateTabCounts();
        
        // Show success message
        this.showNotification('Question deleted successfully!', 'success');
    }

    handleQuestionRestored(question) {
        // Remove from deleted list
        this.deletedQuestions = this.deletedQuestions.filter(q => q.id !== question.id);
        
        // Add back to in-progress list and keep newest first
        this.inProgressQuestions = this.sortNewestFirst([question, ...this.inProgressQuestions]);
        
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
