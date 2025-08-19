const API_BASE_URL = '';

class API {
    static async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${error.message}`);
            throw error;
        }
    }

    static async generateQuestions(data) {
        return this.request('/generate', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    static async improveQuestion(questionId, comment) {
        return this.request('/improve', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
                comment: comment,
            }),
        });
    }

    static async approveQuestion(questionId) {
        return this.request('/approve', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
            }),
        });
    }

    static async deleteQuestion(questionId) {
        return this.request('/delete', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
            }),
        });
    }

    static async exportQuestion(questionId) {
        return this.request('/export', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
            }),
        });
    }

    static async downloadCSV() {
        const response = await fetch(`${API_BASE_URL}/csv`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const dispo = response.headers.get('Content-Disposition') || '';
        const match = dispo.match(/filename="?([^";]+)"?/i);
        const filename = match ? match[1] : 'export.csv';

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    static async listCsvFiles() {
        return this.request('/csv/list', { method: 'GET' });
    }

    static async downloadCsvFile(filename) {
        const response = await fetch(`${API_BASE_URL}/csv/file/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const dispo = response.headers.get('Content-Disposition') || '';
        const match = dispo.match(/filename="?([^";]+)"?/i);
        const suggested = match ? match[1] : filename || 'export.csv';

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = suggested;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    static async getQuestions(status = null) {
        const endpoint = status ? `/questions?status=${status}` : '/questions';
        return this.request(endpoint, {
            method: 'GET',
        });
    }

    static async unapproveQuestion(questionId) {
        return this.request('/unapprove', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
            }),
        });
    }

    static async undeleteQuestion(questionId) {
        return this.request('/undelete', {
            method: 'POST',
            body: JSON.stringify({
                question_id: questionId,
            }),
        });
    }

    static async canExportQuestion(questionId) {
        return this.request(`/can-export/${questionId}`, {
            method: 'GET',
        });
    }
}

export default API;
