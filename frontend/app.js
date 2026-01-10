/**
 * Vault AI - Frontend Application
 * Handles all API integrations and UI interactions
 */

// ========================================
// Configuration
// ========================================
const API_BASE = '/api/v1';
const POLLING_INTERVAL = 5000;

// ========================================
// State Management
// ========================================
const state = {
    currentPage: 'dashboard',
    documents: {
        items: [],
        total: 0,
        page: 1,
        pageSize: 12,
        totalPages: 0,
        filters: {
            search: '',
            status: '',
            type: ''
        }
    },
    currentDocument: null,
    chat: {
        sessions: [],
        currentSession: null,
        messages: []
    },
    health: null,
    stats: null,
    processingPolling: null
};

// ========================================
// API Client
// ========================================
const api = {
    async get(endpoint) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.message || 'Request failed');
            }
            return response.json();
        } catch (error) {
            console.error(`GET ${endpoint} failed:`, error);
            throw error;
        }
    },
    
    async post(endpoint, data, isFormData = false) {
        try {
            const options = {
                method: 'POST',
                body: isFormData ? data : JSON.stringify(data)
            };
            if (!isFormData) {
                options.headers = { 'Content-Type': 'application/json' };
            }
            const response = await fetch(`${API_BASE}${endpoint}`, options);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.message || 'Request failed');
            }
            return response.json();
        } catch (error) {
            console.error(`POST ${endpoint} failed:`, error);
            throw error;
        }
    },
    
    async delete(endpoint) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.message || 'Request failed');
            }
            return response.json();
        } catch (error) {
            console.error(`DELETE ${endpoint} failed:`, error);
            throw error;
        }
    }
};

// ========================================
// Utility Functions
// ========================================
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatCurrency(amount) {
    return '$' + amount.toFixed(4);
}

function getFileTypeIcon(type) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
    </svg>`;
}

function getStatusClass(status) {
    const statusMap = {
        'completed': 'status-completed',
        'processing': 'status-processing',
        'pending': 'status-pending',
        'failed': 'status-failed'
    };
    return statusMap[status] || 'status-pending';
}

// ========================================
// Toast Notifications
// ========================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ========================================
// Navigation
// ========================================
function navigateTo(page) {
    state.currentPage = page;
    
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // Update pages
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `${page}Page`);
    });
    
    // Update page title
    const titles = {
        dashboard: 'Dashboard',
        documents: 'Documents',
        documentDetail: 'Document Details',
        chat: 'Chat',
        metrics: 'Metrics'
    };
    document.getElementById('pageTitle').textContent = titles[page] || 'Dashboard';
    
    // Show/hide upload button
    document.getElementById('uploadBtn').style.display = 
        page === 'documents' ? 'flex' : 'none';
    
    // Load page data
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'documents':
            loadDocuments();
            break;
        case 'chat':
            loadChatSessions();
            break;
        case 'metrics':
            loadMetrics();
            break;
    }
}

// ========================================
// Dashboard
// ========================================
async function loadDashboard() {
    try {
        const [health, stats] = await Promise.all([
            api.get('/health/detailed'),
            api.get('/metrics/documents')
        ]);
        
        state.health = health;
        state.stats = stats;
        
        renderHealth(health);
        renderStats(stats);
        renderRecentDocuments(stats.recent_documents);
        renderCategories(stats.top_categories);
    } catch (error) {
        showToast('Failed to load dashboard data', 'error');
    }
}

function renderHealth(health) {
    // Update sidebar indicator
    const indicator = document.getElementById('systemHealth');
    const dot = indicator.querySelector('.health-dot');
    const text = indicator.querySelector('.health-text');
    
    dot.className = `health-dot ${health.status}`;
    text.textContent = health.status.charAt(0).toUpperCase() + health.status.slice(1);
    
    // Update health grid
    const grid = document.getElementById('healthGrid');
    const components = ['database', 'redis', 'storage', 'gemini_api'];
    
    grid.innerHTML = components.map(comp => {
        const data = health[comp] || { status: 'unknown' };
        const statusClass = data.status === 'healthy' ? 'healthy' : 
                          data.status === 'degraded' ? 'degraded' :
                          data.status === 'configured' ? 'healthy' : 'unknown';
        const latency = data.latency_ms ? `${data.latency_ms}ms` : data.status;
        
        return `
            <div class="health-item">
                <span class="health-item-dot ${statusClass}"></span>
                <div class="health-item-content">
                    <div class="health-item-name">${comp.replace('_', ' ')}</div>
                    <div class="health-item-status">${latency}</div>
                </div>
            </div>
        `;
    }).join('');
}

function renderStats(stats) {
    document.getElementById('totalDocuments').textContent = formatNumber(stats.document_stats.total_documents);
    document.getElementById('totalSessions').textContent = formatNumber(stats.chat_stats.total_sessions);
    document.getElementById('totalPages').textContent = formatNumber(stats.document_stats.total_pages);
    document.getElementById('totalTokens').textContent = formatNumber(stats.chat_stats.total_tokens_used);
}

function renderRecentDocuments(documents) {
    const container = document.getElementById('recentDocuments');
    
    if (!documents || documents.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 2rem;">
                <p style="color: var(--text-muted);">No documents yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = documents.slice(0, 5).map(doc => `
        <div class="recent-item" onclick="viewDocument('${doc.id}')">
            <div class="recent-item-icon">
                ${getFileTypeIcon(doc.file_type)}
            </div>
            <div class="recent-item-content">
                <div class="recent-item-name">${doc.original_filename || doc.filename}</div>
                <div class="recent-item-meta">${formatDate(doc.created_at)}</div>
            </div>
            <span class="recent-item-status ${getStatusClass(doc.status)}">${doc.status}</span>
        </div>
    `).join('');
}

function renderCategories(categories) {
    const container = document.getElementById('topCategories');
    
    if (!categories || categories.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 2rem;">
                <p style="color: var(--text-muted);">No categories yet</p>
            </div>
        `;
        return;
    }
    
    const maxCount = Math.max(...categories.map(c => c.count));
    
    container.innerHTML = categories.slice(0, 5).map(cat => `
        <div class="category-item">
            <span class="category-name">${cat.category}</span>
            <div class="category-bar">
                <div class="category-bar-fill" style="width: ${(cat.count / maxCount) * 100}%"></div>
            </div>
            <span class="category-count">${cat.count}</span>
        </div>
    `).join('');
}

async function refreshHealth() {
    try {
        const health = await api.get('/health/detailed');
        state.health = health;
        renderHealth(health);
        showToast('Health status refreshed', 'success');
    } catch (error) {
        showToast('Failed to refresh health', 'error');
    }
}

// ========================================
// Documents
// ========================================
async function loadDocuments() {
    try {
        const { search, status, type } = state.documents.filters;
        let endpoint = `/documents/?page=${state.documents.page}&page_size=${state.documents.pageSize}`;
        
        if (search) endpoint += `&search=${encodeURIComponent(search)}`;
        if (status) endpoint += `&status=${status}`;
        if (type) endpoint += `&file_type=${type}`;
        
        const data = await api.get(endpoint);
        
        state.documents.items = data.documents;
        state.documents.total = data.total;
        state.documents.totalPages = data.total_pages;
        
        renderDocuments();
        renderPagination();
    } catch (error) {
        showToast('Failed to load documents', 'error');
    }
}

function renderDocuments() {
    const container = document.getElementById('documentsGrid');
    const docs = state.documents.items;
    
    if (docs.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <h3>No documents found</h3>
                <p>Upload your first document to get started</p>
                <button class="btn btn-primary" onclick="openUploadModal()">Upload Document</button>
            </div>
        `;
        return;
    }
    
    container.innerHTML = docs.map(doc => `
        <div class="document-card" onclick="viewDocument('${doc.id}')">
            <div class="document-card-header">
                <div class="document-card-icon ${doc.file_type}">
                    ${getFileTypeIcon(doc.file_type)}
                </div>
                <div class="document-card-title">
                    <h3>${doc.title || doc.original_filename}</h3>
                    <span>${doc.file_type.toUpperCase()} • ${formatBytes(doc.file_size)}</span>
                </div>
                <span class="document-card-status ${getStatusClass(doc.status)}">${doc.status}</span>
            </div>
            <div class="document-card-body">
                ${doc.summary || doc.description || 'No description available'}
            </div>
            <div class="document-card-meta">
                <span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                        <line x1="16" y1="2" x2="16" y2="6"/>
                        <line x1="8" y1="2" x2="8" y2="6"/>
                        <line x1="3" y1="10" x2="21" y2="10"/>
                    </svg>
                    ${formatDate(doc.created_at)}
                </span>
                ${doc.page_count ? `
                    <span>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                        </svg>
                        ${doc.page_count} pages
                    </span>
                ` : ''}
                ${doc.word_count ? `
                    <span>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="4 7 4 4 20 4 20 7"/>
                            <line x1="9" y1="20" x2="15" y2="20"/>
                            <line x1="12" y1="4" x2="12" y2="20"/>
                        </svg>
                        ${formatNumber(doc.word_count)} words
                    </span>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function renderPagination() {
    const container = document.getElementById('pagination');
    const { page, totalPages } = state.documents;
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = `
        <button class="pagination-btn" onclick="goToPage(${page - 1})" ${page === 1 ? 'disabled' : ''}>
            Prev
        </button>
    `;
    
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
            html += `
                <button class="pagination-btn ${i === page ? 'active' : ''}" onclick="goToPage(${i})">
                    ${i}
                </button>
            `;
        } else if (i === page - 2 || i === page + 2) {
            html += '<span style="color: var(--text-muted);">...</span>';
        }
    }
    
    html += `
        <button class="pagination-btn" onclick="goToPage(${page + 1})" ${page === totalPages ? 'disabled' : ''}>
            Next
        </button>
    `;
    
    container.innerHTML = html;
}

function goToPage(page) {
    if (page < 1 || page > state.documents.totalPages) return;
    state.documents.page = page;
    loadDocuments();
}

// ========================================
// Document Detail
// ========================================
async function viewDocument(id) {
    try {
        const [doc, analysis] = await Promise.all([
            api.get(`/documents/${id}`),
            api.get(`/documents/${id}/analysis`).catch(() => null)
        ]);
        
        state.currentDocument = { ...doc, analysis };
        renderDocumentDetail();
        navigateTo('documentDetail');
        
        // Start polling if document is processing
        if (doc.status === 'processing' || doc.status === 'pending') {
            startProcessingPolling(id);
        }
    } catch (error) {
        showToast('Failed to load document', 'error');
    }
}

function renderDocumentDetail() {
    const doc = state.currentDocument;
    const container = document.getElementById('documentDetail');
    
    const analysis = doc.analysis || {};
    
    container.innerHTML = `
        <div class="detail-main">
            <div class="card">
                <div class="card-body">
                    <div class="detail-overview">
                        <div class="detail-icon document-card-icon ${doc.file_type}">
                            ${getFileTypeIcon(doc.file_type)}
                        </div>
                        <div class="detail-info">
                            <h2>${doc.title || doc.original_filename}</h2>
                            <p>${doc.description || 'No description provided'}</p>
                            <div class="detail-tags">
                                <span class="detail-tag">${doc.file_type.toUpperCase()}</span>
                                <span class="detail-tag">${formatBytes(doc.file_size)}</span>
                                <span class="detail-tag ${getStatusClass(doc.status)}">${doc.status}</span>
                                ${doc.language ? `<span class="detail-tag">${doc.language.toUpperCase()}</span>` : ''}
                            </div>
                            <div class="detail-actions">
                                ${doc.status === 'completed' ? `
                                    <button class="btn btn-primary" onclick="startChatWithDocument('${doc.id}')">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                                        </svg>
                                        Chat with Document
                                    </button>
                                ` : ''}
                                ${doc.status === 'failed' ? `
                                    <button class="btn btn-primary" onclick="reprocessDocument('${doc.id}')">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="23 4 23 10 17 10"/>
                                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                                        </svg>
                                        Reprocess
                                    </button>
                                ` : ''}
                                <button class="btn btn-ghost" onclick="deleteDocument('${doc.id}')">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="3 6 5 6 21 6"/>
                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                    </svg>
                                    Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h2>Statistics</h2>
                </div>
                <div class="card-body">
                    <div class="detail-stats-grid">
                        <div class="detail-stat">
                            <div class="detail-stat-value">${doc.page_count || 0}</div>
                            <div class="detail-stat-label">Pages</div>
                        </div>
                        <div class="detail-stat">
                            <div class="detail-stat-value">${formatNumber(doc.word_count || 0)}</div>
                            <div class="detail-stat-label">Words</div>
                        </div>
                        <div class="detail-stat">
                            <div class="detail-stat-value">${doc.chunk_count || 0}</div>
                            <div class="detail-stat-label">Chunks</div>
                        </div>
                    </div>
                </div>
            </div>
            
            ${doc.summary ? `
                <div class="card">
                    <div class="card-header">
                        <h2>Summary</h2>
                    </div>
                    <div class="card-body">
                        <p class="summary-text">${doc.summary}</p>
                    </div>
                </div>
            ` : ''}
            
            ${analysis.insights && analysis.insights.length > 0 ? `
                <div class="card">
                    <div class="card-header">
                        <h2>AI Insights</h2>
                    </div>
                    <div class="card-body">
                        <div class="insights-list">
                            ${analysis.insights.map(insight => `
                                <div class="insight-item">
                                    <div class="insight-type">${insight.insight_type}</div>
                                    <div class="insight-content">${insight.content}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            ` : ''}
        </div>
        
        <div class="detail-sidebar">
            ${doc.key_topics && doc.key_topics.length > 0 ? `
                <div class="card">
                    <div class="card-header">
                        <h2>Key Topics</h2>
                    </div>
                    <div class="card-body">
                        <div class="topics-list">
                            ${doc.key_topics.map(topic => `<span class="topic-tag">${topic}</span>`).join('')}
                        </div>
                    </div>
                </div>
            ` : ''}
            
            ${doc.categories && doc.categories.length > 0 ? `
                <div class="card">
                    <div class="card-header">
                        <h2>Categories</h2>
                    </div>
                    <div class="card-body">
                        <div class="categories-list-detail">
                            ${doc.categories.map(cat => `<span class="category-tag">${cat}</span>`).join('')}
                        </div>
                    </div>
                </div>
            ` : ''}
            
            <div class="card">
                <div class="card-header">
                    <h2>Processing Info</h2>
                </div>
                <div class="card-body">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">
                        <p><strong>Created:</strong> ${new Date(doc.created_at).toLocaleString()}</p>
                        ${doc.processing_started_at ? `<p><strong>Processing Started:</strong> ${new Date(doc.processing_started_at).toLocaleString()}</p>` : ''}
                        ${doc.processing_completed_at ? `<p><strong>Completed:</strong> ${new Date(doc.processing_completed_at).toLocaleString()}</p>` : ''}
                        ${doc.processing_duration_ms ? `<p><strong>Duration:</strong> ${(doc.processing_duration_ms / 1000).toFixed(2)}s</p>` : ''}
                        ${doc.processing_error ? `<p style="color: var(--error);"><strong>Error:</strong> ${doc.processing_error}</p>` : ''}
                        ${doc.embedding_model ? `<p><strong>Embedding Model:</strong> ${doc.embedding_model}</p>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function startProcessingPolling(docId) {
    if (state.processingPolling) {
        clearInterval(state.processingPolling);
    }
    
    state.processingPolling = setInterval(async () => {
        try {
            const status = await api.get(`/documents/${docId}/status`);
            
            if (status.status === 'completed' || status.status === 'failed') {
                clearInterval(state.processingPolling);
                state.processingPolling = null;
                
                // Refresh the document
                const doc = await api.get(`/documents/${docId}`);
                const analysis = await api.get(`/documents/${docId}/analysis`).catch(() => null);
                state.currentDocument = { ...doc, analysis };
                renderDocumentDetail();
                
                if (status.status === 'completed') {
                    showToast('Document processing completed!', 'success');
                } else {
                    showToast('Document processing failed', 'error');
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, POLLING_INTERVAL);
}

async function reprocessDocument(id) {
    try {
        await api.post(`/documents/${id}/reprocess`);
        showToast('Document queued for reprocessing', 'success');
        viewDocument(id);
    } catch (error) {
        showToast('Failed to reprocess document', 'error');
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
        return;
    }
    
    try {
        await api.delete(`/documents/${id}`);
        showToast('Document deleted successfully', 'success');
        navigateTo('documents');
    } catch (error) {
        showToast('Failed to delete document', 'error');
    }
}

// ========================================
// Upload
// ========================================
let selectedFile = null;

function openUploadModal() {
    document.getElementById('uploadModal').classList.add('active');
}

function closeUploadModal() {
    document.getElementById('uploadModal').classList.remove('active');
    clearFileSelection();
    document.getElementById('docTitle').value = '';
    document.getElementById('docDescription').value = '';
}

function clearFileSelection() {
    selectedFile = null;
    document.getElementById('uploadZone').style.display = 'block';
    document.getElementById('uploadPreview').style.display = 'none';
    document.getElementById('uploadSubmitBtn').disabled = true;
    document.getElementById('fileInput').value = '';
}

function handleFileSelect(file) {
    if (!file) return;
    
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown'];
    const allowedExtensions = ['.pdf', '.docx', '.txt', '.md'];
    
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
        showToast('Unsupported file type. Please upload PDF, DOCX, TXT, or MD files.', 'error');
        return;
    }
    
    selectedFile = file;
    
    document.getElementById('uploadZone').style.display = 'none';
    document.getElementById('uploadPreview').style.display = 'block';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatBytes(file.size);
    document.getElementById('uploadSubmitBtn').disabled = false;
}

async function uploadDocument() {
    if (!selectedFile) return;
    
    const submitBtn = document.getElementById('uploadSubmitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');
    
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoader.style.display = 'inline-flex';
    
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        const title = document.getElementById('docTitle').value.trim();
        const description = document.getElementById('docDescription').value.trim();
        
        if (title) formData.append('title', title);
        if (description) formData.append('description', description);
        
        const result = await api.post('/documents/upload', formData, true);
        
        showToast('Document uploaded successfully!', 'success');
        closeUploadModal();
        
        // Navigate to document detail
        viewDocument(result.id);
    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

// ========================================
// Chat
// ========================================
async function loadChatSessions() {
    try {
        const sessions = await api.get('/chat/sessions?active_only=false&page_size=50');
        state.chat.sessions = sessions;
        renderChatSessions();
    } catch (error) {
        showToast('Failed to load chat sessions', 'error');
    }
}

function renderChatSessions() {
    const container = document.getElementById('sessionsList');
    const sessions = state.chat.sessions;
    
    if (sessions.length === 0) {
        container.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--text-muted);">
                <p>No chat sessions yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = sessions.map(session => `
        <div class="session-item ${state.chat.currentSession?.id === session.id ? 'active' : ''}" 
             onclick="selectChatSession('${session.id}')">
            <div class="session-title">${session.title || 'Untitled Chat'}</div>
            <div class="session-meta">${session.message_count} messages • ${formatDate(session.updated_at || session.created_at)}</div>
        </div>
    `).join('');
}

async function selectChatSession(sessionId) {
    try {
        const [session, history] = await Promise.all([
            api.get(`/chat/sessions/${sessionId}`),
            api.get(`/chat/sessions/${sessionId}/history`)
        ]);
        
        state.chat.currentSession = session;
        state.chat.messages = history.messages;
        
        renderChatSessions();
        renderChatView();
    } catch (error) {
        showToast('Failed to load chat session', 'error');
    }
}

function renderChatView() {
    const session = state.chat.currentSession;
    const messages = state.chat.messages;
    
    document.getElementById('chatEmpty').style.display = 'none';
    document.getElementById('chatActive').style.display = 'flex';
    
    // Render header
    document.getElementById('chatHeader').innerHTML = `
        <div class="chat-header-info">
            <h3>${session.title || 'Untitled Chat'}</h3>
            <span>${session.message_count} messages • ${formatNumber(session.total_tokens_used)} tokens used</span>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="closeChatSession('${session.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            Close Session
        </button>
    `;
    
    // Render messages
    const messagesContainer = document.getElementById('chatMessages');
    
    if (messages.length === 0) {
        messagesContainer.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 2rem;">
                <p>Start the conversation by asking a question about your document.</p>
            </div>
        `;
    } else {
        messagesContainer.innerHTML = messages.map(msg => `
            <div class="message ${msg.role}">
                <div class="message-avatar">
                    ${msg.role === 'user' ? 
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>' :
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>'
                    }
                </div>
                <div class="message-content">
                    <div class="message-text">${formatMessageContent(msg.content)}</div>
                    ${msg.citations && msg.citations.length > 0 ? `
                        <div class="message-citations">
                            <div class="message-citations-title">Sources</div>
                            ${msg.citations.map(c => `
                                <div class="citation-item">
                                    ${c.content_snippet}
                                    ${c.page_number ? `<span style="color: var(--text-muted);"> (Page ${c.page_number})</span>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${msg.role === 'assistant' && msg.response_time_ms ? `
                        <div class="message-meta">${msg.response_time_ms}ms • ${msg.total_tokens} tokens</div>
                    ` : ''}
                </div>
            </div>
        `).join('');
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Render suggestions
    const lastAssistantMsg = messages.filter(m => m.role === 'assistant').pop();
    const suggestionsContainer = document.getElementById('suggestedQuestions');
    
    if (lastAssistantMsg?.suggested_questions?.length > 0) {
        suggestionsContainer.innerHTML = lastAssistantMsg.suggested_questions.map(q => 
            `<button class="suggestion-btn" onclick="askSuggestedQuestion('${escapeHtml(q)}')">${q}</button>`
        ).join('');
    } else {
        suggestionsContainer.innerHTML = '';
    }
}

function formatMessageContent(content) {
    // Basic markdown-like formatting
    return content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, "\\'");
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    
    if (!question || !state.chat.currentSession) return;
    
    const sessionId = state.chat.currentSession.id;
    
    // Add user message to UI immediately
    state.chat.messages.push({
        id: 'temp-' + Date.now(),
        role: 'user',
        content: question,
        created_at: new Date().toISOString()
    });
    renderChatView();
    
    // Clear input
    input.value = '';
    document.getElementById('sendBtn').disabled = true;
    
    // Add loading indicator
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML += `
        <div class="message assistant" id="loadingMessage">
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-text">
                    <span class="skeleton" style="display: inline-block; width: 200px; height: 20px;"></span>
                </div>
            </div>
        </div>
    `;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    try {
        const response = await api.post(`/chat/sessions/${sessionId}/ask`, {
            question: question,
            include_citations: true,
            include_suggestions: true
        });
        
        // Remove loading and add real response
        state.chat.messages.push(response.message);
        state.chat.currentSession.message_count += 2;
        state.chat.currentSession.total_tokens_used += response.message.total_tokens;
        
        renderChatView();
    } catch (error) {
        document.getElementById('loadingMessage')?.remove();
        showToast(`Failed to get response: ${error.message}`, 'error');
    }
}

function askSuggestedQuestion(question) {
    document.getElementById('chatInput').value = question;
    sendMessage();
}

async function closeChatSession(sessionId) {
    try {
        await api.delete(`/chat/sessions/${sessionId}`);
        state.chat.currentSession = null;
        state.chat.messages = [];
        
        document.getElementById('chatEmpty').style.display = 'flex';
        document.getElementById('chatActive').style.display = 'none';
        
        loadChatSessions();
        showToast('Chat session closed', 'success');
    } catch (error) {
        showToast('Failed to close session', 'error');
    }
}

function openNewChatModal() {
    // Load completed documents for selection
    loadDocumentsForChat();
    document.getElementById('newChatModal').classList.add('active');
}

function closeNewChatModal() {
    document.getElementById('newChatModal').classList.remove('active');
    document.getElementById('chatDocSelect').value = '';
    document.getElementById('chatTitle').value = '';
    document.getElementById('startChatBtn').disabled = true;
}

async function loadDocumentsForChat() {
    try {
        const data = await api.get('/documents/?status=completed&page_size=100');
        const select = document.getElementById('chatDocSelect');
        
        select.innerHTML = '<option value="">Choose a document...</option>';
        data.documents.forEach(doc => {
            select.innerHTML += `<option value="${doc.id}">${doc.title || doc.original_filename}</option>`;
        });
    } catch (error) {
        showToast('Failed to load documents', 'error');
    }
}

async function startNewChat() {
    const docId = document.getElementById('chatDocSelect').value;
    const title = document.getElementById('chatTitle').value.trim();
    
    if (!docId) return;
    
    try {
        const session = await api.post('/chat/sessions', {
            document_id: docId,
            title: title || null
        });
        
        closeNewChatModal();
        state.chat.sessions.unshift(session);
        await selectChatSession(session.id);
        showToast('Chat session created!', 'success');
    } catch (error) {
        showToast(`Failed to create chat: ${error.message}`, 'error');
    }
}

async function startChatWithDocument(docId) {
    try {
        const doc = state.currentDocument;
        const session = await api.post('/chat/sessions', {
            document_id: docId,
            title: `Chat about ${doc.title || doc.original_filename}`
        });
        
        navigateTo('chat');
        state.chat.sessions.unshift(session);
        await selectChatSession(session.id);
        showToast('Chat session created!', 'success');
    } catch (error) {
        showToast(`Failed to create chat: ${error.message}`, 'error');
    }
}

// ========================================
// Metrics
// ========================================
async function loadMetrics() {
    try {
        const hours = document.getElementById('metricsTimeRange').value;
        const [processing, costs] = await Promise.all([
            api.get(`/metrics/processing?hours=${hours}`),
            api.get('/metrics/costs')
        ]);
        
        renderCostStats(costs);
        renderProcessingStats(processing);
        renderRecentMetrics(processing.recent_metrics);
    } catch (error) {
        showToast('Failed to load metrics', 'error');
    }
}

function renderCostStats(costs) {
    const container = document.getElementById('costStats');
    
    container.innerHTML = `
        <div class="cost-stat">
            <div class="cost-stat-value">${formatCurrency(costs.total_cost)}</div>
            <div class="cost-stat-label">Total Cost</div>
        </div>
        <div class="cost-stat">
            <div class="cost-stat-value">${formatCurrency(costs.cost_today)}</div>
            <div class="cost-stat-label">Today</div>
        </div>
        <div class="cost-stat">
            <div class="cost-stat-value">${formatCurrency(costs.cost_this_week)}</div>
            <div class="cost-stat-label">This Week</div>
        </div>
        <div class="cost-stat">
            <div class="cost-stat-value">${formatCurrency(costs.cost_this_month)}</div>
            <div class="cost-stat-label">This Month</div>
        </div>
    `;
}

function renderProcessingStats(processing) {
    const container = document.getElementById('processingStats');
    const stats = processing.stats;
    
    const successRate = stats.total_operations > 0 
        ? (stats.successful_operations / stats.total_operations * 100).toFixed(1)
        : 0;
    
    container.innerHTML = `
        <div class="processing-stat">
            <div class="processing-stat-header">
                <span class="processing-stat-label">Total Operations</span>
            </div>
            <div class="processing-stat-value">${formatNumber(stats.total_operations)}</div>
        </div>
        <div class="processing-stat">
            <div class="processing-stat-header">
                <span class="processing-stat-label">Success Rate</span>
            </div>
            <div class="processing-stat-value" style="color: ${successRate >= 90 ? 'var(--success)' : successRate >= 70 ? 'var(--warning)' : 'var(--error)'}">
                ${successRate}%
            </div>
            <div class="processing-stat-bar">
                <div class="processing-stat-fill" style="width: ${successRate}%"></div>
            </div>
        </div>
        <div class="processing-stat">
            <div class="processing-stat-header">
                <span class="processing-stat-label">Avg Duration</span>
            </div>
            <div class="processing-stat-value">${(stats.average_duration_ms / 1000).toFixed(2)}s</div>
        </div>
        <div class="processing-stat">
            <div class="processing-stat-header">
                <span class="processing-stat-label">Total Tokens</span>
            </div>
            <div class="processing-stat-value">${formatNumber(stats.total_tokens_used)}</div>
        </div>
    `;
}

function renderRecentMetrics(metrics) {
    const table = document.getElementById('recentMetrics');
    
    if (!metrics || metrics.length === 0) {
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Operation</th>
                    <th>Type</th>
                    <th>Duration</th>
                    <th>Status</th>
                    <th>Tokens</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        No recent operations
                    </td>
                </tr>
            </tbody>
        `;
        return;
    }
    
    table.innerHTML = `
        <thead>
            <tr>
                <th>Operation</th>
                <th>Type</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Tokens</th>
                <th>Time</th>
            </tr>
        </thead>
        <tbody>
            ${metrics.map(m => `
                <tr>
                    <td>${m.operation_name}</td>
                    <td><span class="detail-tag">${m.metric_type}</span></td>
                    <td class="mono">${m.duration_ms ? (m.duration_ms / 1000).toFixed(2) + 's' : '-'}</td>
                    <td>
                        <span class="${m.success ? 'status-completed' : 'status-failed'}" 
                              style="padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">
                            ${m.success ? 'Success' : 'Failed'}
                        </span>
                    </td>
                    <td class="mono">${formatNumber(m.tokens_used)}</td>
                    <td>${formatDate(m.started_at)}</td>
                </tr>
            `).join('')}
        </tbody>
    `;
}

// ========================================
// Event Listeners
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navigateTo(item.dataset.page);
        });
    });
    
    // Upload button
    document.getElementById('uploadBtn').addEventListener('click', openUploadModal);
    
    // Upload zone
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFileSelect(e.dataTransfer.files[0]);
    });
    
    fileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
    });
    
    // Upload submit
    document.getElementById('uploadSubmitBtn').addEventListener('click', uploadDocument);
    
    // Search and filters
    let searchTimeout;
    document.getElementById('searchInput').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.documents.filters.search = e.target.value;
            state.documents.page = 1;
            loadDocuments();
        }, 300);
    });
    
    document.getElementById('statusFilter').addEventListener('change', (e) => {
        state.documents.filters.status = e.target.value;
        state.documents.page = 1;
        loadDocuments();
    });
    
    document.getElementById('typeFilter').addEventListener('change', (e) => {
        state.documents.filters.type = e.target.value;
        state.documents.page = 1;
        loadDocuments();
    });
    
    // Chat
    document.getElementById('newChatBtn').addEventListener('click', openNewChatModal);
    
    document.getElementById('chatDocSelect').addEventListener('change', (e) => {
        document.getElementById('startChatBtn').disabled = !e.target.value;
    });
    
    document.getElementById('startChatBtn').addEventListener('click', startNewChat);
    
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    
    chatInput.addEventListener('input', () => {
        sendBtn.disabled = !chatInput.value.trim();
        // Auto-resize
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });
    
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (chatInput.value.trim()) {
                sendMessage();
            }
        }
    });
    
    sendBtn.addEventListener('click', sendMessage);
    
    // Metrics time range
    document.getElementById('metricsTimeRange').addEventListener('change', loadMetrics);
    
    // Initial load
    loadDashboard();
    
    // Periodic health check
    setInterval(async () => {
        try {
            const health = await api.get('/health/');
            const indicator = document.getElementById('systemHealth');
            const dot = indicator.querySelector('.health-dot');
            const text = indicator.querySelector('.health-text');
            
            dot.className = `health-dot ${health.status}`;
            text.textContent = health.status.charAt(0).toUpperCase() + health.status.slice(1);
        } catch (error) {
            console.error('Health check failed:', error);
        }
    }, 30000);
});

// Make functions globally available
window.navigateTo = navigateTo;
window.viewDocument = viewDocument;
window.refreshHealth = refreshHealth;
window.openUploadModal = openUploadModal;
window.closeUploadModal = closeUploadModal;
window.clearFileSelection = clearFileSelection;
window.goToPage = goToPage;
window.reprocessDocument = reprocessDocument;
window.deleteDocument = deleteDocument;
window.selectChatSession = selectChatSession;
window.closeChatSession = closeChatSession;
window.closeNewChatModal = closeNewChatModal;
window.startChatWithDocument = startChatWithDocument;
window.askSuggestedQuestion = askSuggestedQuestion;

