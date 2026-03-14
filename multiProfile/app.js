// app.js
document.addEventListener('DOMContentLoaded', () => {
    const appContainer = document.getElementById('app-container');
    const data = window.viJoonData;

    // HTML 이스케이프 헬퍼 (XSS 방지)
    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // URL 검증 헬퍼 (javascript: 프로토콜 차단)
    function safeURL(url) {
        if (!url) return '#';
        const trimmed = url.trim();
        if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed) || /^\.?\//i.test(trimmed) || trimmed === '#') {
            return escapeHTML(trimmed);
        }
        return '#';
    }

    // 1. 초기 렌더링 함수
    function renderApp() {
        appContainer.innerHTML = ''; // 초기화

        // --- Header Section ---
        const headerHTML = `
            <header class="flex flex-col items-center mb-8 animate-fade-in">
                <div class="relative w-24 h-24 mb-4 rounded-full neon-border overflow-hidden">
                    <img src="${escapeHTML(data.profile.image)}" alt="Profile Image" class="w-full h-full object-cover">
                </div>
                <h1 class="text-2xl font-bold mb-2 text-neon">${escapeHTML(data.profile.title)}</h1>
                <p class="text-gray-400 text-center text-sm px-4">${escapeHTML(data.profile.description)}</p>
            </header>
        `;

        // --- Featured Area (Highlight CTA) ---
        let featuredHTML = '';
        if (data.featured && data.featured.isActive) {
            featuredHTML = `
                <section class="mb-8 w-full">
                    <a href="${safeURL(data.featured.link)}" target="_blank" rel="noopener noreferrer"
                       class="block w-full py-4 px-6 text-center font-bold text-white rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 shadow-lg hover-neon transition-all-300 transform active:scale-95">
                        ${escapeHTML(data.featured.title)}
                    </a>
                </section>
            `;
        }

        // --- Project Grid ---
        const projectsHTML = `
            <section class="space-y-4 w-full" id="project-list">
                ${data.projects.map(proj => `
                    <a href="${safeURL(proj.url)}" target="_blank" rel="noopener noreferrer"
                       class="glass-panel rounded-xl p-4 flex items-center space-x-4 hover:bg-white/10 hover-neon transition-all-300 transform active:scale-95" data-id="${escapeHTML(proj.id)}">
                        <div class="w-16 h-16 shrink-0 rounded-lg overflow-hidden bg-gray-800">
                            <img src="${escapeHTML(proj.thumbnail)}" alt="${escapeHTML(proj.title)}" class="w-full h-full object-cover">
                        </div>
                        <div class="flex-1 min-w-0">
                            <h2 class="text-lg font-semibold text-white truncate">${escapeHTML(proj.title)}</h2>
                            <p class="text-sm text-gray-400 line-clamp-2">${escapeHTML(proj.description)}</p>
                            <div class="flex flex-wrap gap-2 mt-2">
                                ${(proj.tags || []).map(tag => `<span class="text-xs bg-purple-900/50 text-purple-200 px-2 py-0.5 rounded-full border border-purple-500/30">${escapeHTML(tag)}</span>`).join('')}
                            </div>
                        </div>
                    </a>
                `).join('')}
            </section>
        `;

        // --- Social/Footer ---
        const socialHTML = `
            <footer class="mt-12 mb-8 flex justify-center space-x-6">
                ${data.socials.instagram ? `<a href="${safeURL(data.socials.instagram)}" target="_blank" rel="noopener noreferrer" class="text-gray-400 hover:text-brand-purple transition-all-300"><i class="fab fa-instagram text-2xl"></i> Instagram</a>` : ''}
                ${data.socials.github ? `<a href="${safeURL(data.socials.github)}" target="_blank" rel="noopener noreferrer" class="text-gray-400 hover:text-brand-purple transition-all-300"><i class="fab fa-github text-2xl"></i> Github</a>` : ''}
                ${data.socials.email ? `<a href="${safeURL(data.socials.email)}" class="text-gray-400 hover:text-brand-purple transition-all-300"><i class="fas fa-envelope text-2xl"></i> Email</a>` : ''}
            </footer>
            <p class="text-center text-xs text-gray-600 pb-4 relative z-10 w-full">Press <kbd class="px-1 py-0.5 bg-gray-800 rounded text-gray-400 font-mono">Ctrl + M</kbd> to edit (Local Only)</p>
        `;

        // 조합하여 주입
        appContainer.innerHTML = headerHTML + featuredHTML + projectsHTML + socialHTML;
    }

    // 초기 렌더링 실행
    renderApp();

    // 외부에서 재렌더링 할 수 있도록 window 객체에 할당
    window.renderApp = renderApp;

    // ==========================================
    // Admin Panel Logic (로컬 관리자 기능)
    // ==========================================
    let isAdminOpen = false;

    function initAdminPanel() {
        // 이미 렌더링 되어 있다면 열기만 함
        let adminPanel = document.getElementById('admin-panel');
        if (!adminPanel) {
            // Admin HTML 생성
            adminPanel = document.createElement('div');
            adminPanel.id = 'admin-panel';
            adminPanel.className = 'fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex justify-end transform transition-transform duration-300 translate-x-full';

            // 패널 UI 구성
            adminPanel.innerHTML = `
                <div class="w-full max-w-md h-full bg-gray-900 border-l border-brand-purple/30 p-6 overflow-y-auto shadow-2xl flex flex-col">
                    <div class="flex justify-between items-center mb-6 shrink-0">
                        <h2 class="text-xl font-bold text-white flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-brand-purple shadow-[0_0_8px_#8A2BE2]"></span> Admin Panel</h2>
                        <button id="close-admin" class="text-gray-400 hover:text-white pb-1">&times; Close</button>
                    </div>

                    <!-- Actions -->
                    <div class="flex flex-col gap-2 mb-6 bg-gray-800 p-3 rounded-xl border border-gray-700/50 shrink-0">
                        <div class="flex gap-2">
                             <button id="btn-save-local" class="flex-1 bg-brand-purple hover:bg-purple-600 text-sm py-2 rounded-lg transition shadow-[0_0_15px_rgba(138,43,226,0.3)] text-white font-bold flex items-center justify-center gap-2"><i class="fas fa-save"></i> Save Changes</button>
                             <button id="btn-reset-local" class="bg-gray-700 hover:bg-red-900/40 text-gray-300 hover:text-red-200 text-xs px-3 py-2 rounded-lg transition border border-gray-600 flex items-center justify-center" title="기본값으로 초기화">Reset</button>
                        </div>
                        <div class="h-px bg-gray-700 my-1"></div>
                        <div class="flex gap-2">
                            <button id="btn-copy-json" class="flex-1 bg-gray-700/50 hover:bg-gray-600/50 text-gray-300 text-[10px] py-1.5 rounded-lg transition border border-gray-600/50 uppercase tracking-widest font-bold">Copy to Clipboard</button>
                            <button id="btn-dl-json" class="flex-1 bg-gray-700/50 hover:bg-gray-600/50 text-gray-300 text-[10px] py-1.5 rounded-lg transition border border-gray-600/50 uppercase tracking-widest font-bold">Download JS</button>
                        </div>
                    </div>

                    <!-- Profiles Settings (Pre-existing) -->


                    <!-- Profile Settings -->
                    <div class="mb-6 space-y-3 shrink-0">
                        <h3 class="text-brand-purple font-semibold text-sm border-b border-gray-700 pb-1">Profile</h3>
                        <input type="text" id="edit-profile-title" placeholder="Title" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white focus:outline-none focus:border-brand-purple">
                        <textarea id="edit-profile-desc" placeholder="Description" rows="2" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white focus:outline-none focus:border-brand-purple"></textarea>
                    </div>
                    
                    <!-- Featured Settings -->
                    <div class="mb-6 space-y-3 shrink-0">
                        <div class="flex justify-between items-center border-b border-gray-700 pb-1">
                            <h3 class="text-brand-purple font-semibold text-sm">Featured CTA</h3>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="edit-featured-active" class="sr-only peer">
                                <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-brand-purple"></div>
                            </label>
                        </div>
                        <input type="text" id="edit-featured-title" placeholder="Button Text" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white focus:outline-none focus:border-brand-purple">
                    </div>

                    <!-- Projects List (Sortable via Drag & Drop & Editable) -->
                    <div class="flex-1 mb-2 flex flex-col min-h-0">
                        <div class="flex justify-between items-center border-b border-gray-700 pb-1 mb-3 shrink-0">
                            <h3 class="text-brand-purple font-semibold text-sm">Links (Drag to Reorder)</h3>
                            <button id="btn-add-link" class="text-xs bg-brand-purple text-white px-2 py-1 rounded hover:bg-purple-600 transition shadow-[0_0_5px_#8A2BE2]">+ Add Link</button>
                        </div>
                        <ul id="admin-project-list" class="space-y-3 overflow-y-auto pr-2 pb-4 flex-1"></ul>
                    </div>
                    
                    <p class="text-xs text-gray-500 mt-auto pt-4 text-center shrink-0 border-t border-gray-800">Changes are previewed instantly.<br>Use Export buttons to save permanently.</p>
                </div>
            `;
            document.body.appendChild(adminPanel);
            setupAdminEvents();
        }

        // 뷰어-에디터 데이터 동기화
        syncDataToAdmin();

        // 패널 열기
        requestAnimationFrame(() => {
            adminPanel.classList.remove('translate-x-full');
            isAdminOpen = true;
        });
    }

    function closeAdminPanel() {
        const adminPanel = document.getElementById('admin-panel');
        if (adminPanel) {
            adminPanel.classList.add('translate-x-full');
            isAdminOpen = false;
        }
    }

    function syncDataToAdmin() {
        // Settings (No UI for API Key)

        // 프로필
        document.getElementById('edit-profile-title').value = data.profile.title;
        document.getElementById('edit-profile-desc').value = data.profile.description;

        // Featured
        document.getElementById('edit-featured-active').checked = data.featured.isActive;
        document.getElementById('edit-featured-title').value = data.featured.title;

        // 프로젝트 리스트 (Drag and Drop UI & Edit Form)
        const projListEl = document.getElementById('admin-project-list');
        projListEl.innerHTML = '';
        data.projects.forEach((proj, idx) => {
            const li = document.createElement('li');
            li.draggable = true;
            li.dataset.idx = idx;
            li.className = 'flex flex-col gap-2 bg-gray-800 p-3 rounded border border-gray-700 hover:border-gray-500 transition-colors';

            li.innerHTML = `
                <div class="flex items-center gap-3">
                    <i class="fas fa-grip-vertical text-gray-500 cursor-grab active:cursor-grabbing text-sm px-1 drag-handle hover:text-white transition"></i>
                    <img src="${proj.thumbnail || 'https://via.placeholder.com/150/2C2F33/FFFFFF?text=No+Image'}" class="w-8 h-8 rounded object-cover border border-gray-600">
                    <span class="text-sm truncate flex-1 text-white font-medium proj-title-disp">${proj.title || '(No Title)'}</span>
                    <button class="btn-edit text-blue-400 hover:text-blue-300 transition px-1" title="Edit"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg></button>
                    <button class="btn-delete text-red-400 hover:text-red-300 transition px-1" title="Delete"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>
                </div>
                <div class="edit-form hidden flex-col gap-2 mt-2 pt-3 border-t border-gray-700/50">
                    <label class="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-[-4px]">제목 (Title)</label>
                    <input type="text" class="input-title w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-white placeholder-gray-500 focus:border-brand-purple outline-none" placeholder="Title" value="${proj.title || ''}">
                    
                    <label class="text-[10px] text-gray-400 uppercase font-bold tracking-wider mt-1 mb-[-4px]">연결될 링크 (URL)</label>
                    <input type="text" class="input-url w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-white placeholder-gray-500 focus:border-brand-purple outline-none" placeholder="https://..." value="${proj.url || ''}">
                    
                    <label class="text-[10px] text-gray-400 uppercase font-bold tracking-wider mt-1 mb-[-4px]">설명 (Description)</label>
                    <textarea class="input-desc w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-white placeholder-gray-500 focus:border-brand-purple outline-none" placeholder="Description" rows="2">${proj.description || ''}</textarea>
                    
                    <label class="text-[10px] text-gray-400 uppercase font-bold tracking-wider mt-1 mb-[-4px]">썸네일 이미지 (Image URL)</label>
                    <input type="text" class="input-thumb w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-white placeholder-gray-500 focus:border-brand-purple outline-none" placeholder="https://..." value="${proj.thumbnail || ''}">
                    
                    <label class="text-[10px] text-gray-400 uppercase font-bold tracking-wider mt-1 mb-[-4px]">태그 (Tags, 쉼표 구분)</label>
                    <input type="text" class="input-tags w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-xs text-white placeholder-gray-500 focus:border-brand-purple outline-none" placeholder="예: React, Node.js" value="${(proj.tags || []).join(', ')}">
                </div>
            `;
            projListEl.appendChild(li);
        });

        setupDragAndDrop(projListEl);
    }

    function setupAdminEvents() {
        // Save Changes (LocalStorage)
        document.getElementById('btn-save-local').addEventListener('click', () => {
            localStorage.setItem('viJoonLink_data', JSON.stringify(data));
            alert('변경 사항이 영구적으로 보존되었습니다! (LocalStorage)');
        });

        // Reset
        document.getElementById('btn-reset-local').addEventListener('click', () => {
            if (confirm('모든 변경 사항을 무시하고 소스 코드의 기본값으로 되돌릴까요?')) {
                localStorage.removeItem('viJoonLink_data');
                location.reload();
            }
        });

        // 닫기 버튼
        document.getElementById('close-admin').addEventListener('click', closeAdminPanel);

        // Profile Preview Binding

        document.getElementById('edit-profile-title').addEventListener('input', (e) => {
            data.profile.title = e.target.value;
            renderApp();
        });
        document.getElementById('edit-profile-desc').addEventListener('input', (e) => {
            data.profile.description = e.target.value;
            renderApp();
        });
        document.getElementById('edit-featured-active').addEventListener('change', (e) => {
            data.featured.isActive = e.target.checked;
            renderApp();
        });
        document.getElementById('edit-featured-title').addEventListener('input', (e) => {
            data.featured.title = e.target.value;
            renderApp();
        });

        // Add Link 기능
        document.getElementById('btn-add-link').addEventListener('click', () => {
            data.projects.push({
                id: 'proj-' + Date.now(),
                title: 'New Link',
                description: 'Description for new link.',
                tags: [],
                url: '#',
                thumbnail: 'https://via.placeholder.com/600x400/2C2F33/FFFFFF?text=New+Link'
            });
            renderApp();
            syncDataToAdmin();

            // 새로 추가된 항목 열어주기 & 스크롤 이동
            setTimeout(() => {
                const list = document.getElementById('admin-project-list');
                const lastItem = list.lastElementChild;
                if (lastItem) {
                    const form = lastItem.querySelector('.edit-form');
                    form.classList.remove('hidden');
                    lastItem.querySelector('.btn-edit svg').classList.add('text-brand-purple');
                    list.scrollTop = list.scrollHeight;
                }
            }, 50);
        });

        // 리스트 내 Edit/Delete 클릭 및 Input 변경 이벤트 델리게이션
        const listEl = document.getElementById('admin-project-list');

        listEl.addEventListener('click', (e) => {
            const btnEdit = e.target.closest('.btn-edit');
            const btnDel = e.target.closest('.btn-delete');
            const li = e.target.closest('li');

            if (btnEdit && li) {
                const form = li.querySelector('.edit-form');
                form.classList.toggle('hidden');

                // 다른 폼들은 닫기 (Accordion 스타일)
                if (!form.classList.contains('hidden')) {
                    document.querySelectorAll('#admin-project-list .edit-form').forEach(f => {
                        if (f !== form) f.classList.add('hidden');
                    });
                }
            }

            if (btnDel && li) {
                if (confirm('이 링크를 삭제하시겠습니까? (Are you sure you want to delete this link?)')) {
                    const idx = parseInt(li.dataset.idx, 10);
                    data.projects.splice(idx, 1);
                    renderApp();
                    syncDataToAdmin();
                }
            }
        });

        listEl.addEventListener('input', (e) => {
            const li = e.target.closest('li');
            if (!li) return;
            const idx = parseInt(li.dataset.idx, 10);
            const proj = data.projects[idx];

            if (e.target.classList.contains('input-title')) {
                proj.title = e.target.value;
                li.querySelector('.proj-title-disp').textContent = proj.title || '(No Title)';
            } else if (e.target.classList.contains('input-desc')) {
                proj.description = e.target.value;
            } else if (e.target.classList.contains('input-url')) {
                proj.url = e.target.value;
            } else if (e.target.classList.contains('input-thumb')) {
                proj.thumbnail = e.target.value;
                li.querySelector('img').src = proj.thumbnail || 'https://via.placeholder.com/150/2C2F33/FFFFFF?text=No+Image';
            } else if (e.target.classList.contains('input-tags')) {
                proj.tags = e.target.value.split(',').map(t => t.trim()).filter(t => t);
            }
            renderApp();
        });

        // Export 헬퍼
        function buildExportText() {
            return `const globalData = ${JSON.stringify(data, null, 4)};\n\n// --- LocalStorage Persistence Layer ---\nconst savedData = localStorage.getItem('viJoonLink_data');\nlet finalData;\ntry {\n    finalData = savedData ? JSON.parse(savedData) : globalData;\n} catch (e) {\n    console.warn('LocalStorage data corrupted, using defaults:', e);\n    localStorage.removeItem('viJoonLink_data');\n    finalData = globalData;\n}\n\nwindow.viJoonData = finalData;`;
        }

        // Copy 버튼
        document.getElementById('btn-copy-json').addEventListener('click', () => {
            navigator.clipboard.writeText(buildExportText()).then(() => {
                alert('Copied data.js content to clipboard!');
            });
        });

        // Download 버튼
        document.getElementById('btn-dl-json').addEventListener('click', () => {
            const exportText = buildExportText();
            const blob = new Blob([exportText], { type: 'application/javascript' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'data.js';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    // Drag and Drop Logic (Desktop + Mobile Touch)
    function setupDragAndDrop(listEl) {
        let draggedItem = null;

        // --- Desktop: Native Drag & Drop ---
        listEl.addEventListener('dragstart', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.closest('.edit-form') || e.target.closest('button')) {
                e.preventDefault();
                return;
            }

            draggedItem = e.target.closest('li');
            if (!draggedItem) return;

            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', '');
            setTimeout(() => { if (draggedItem) draggedItem.classList.add('opacity-50'); }, 0);
        });

        listEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const targetItem = e.target.closest('li');
            if (targetItem && targetItem !== draggedItem) {
                const rect = targetItem.getBoundingClientRect();
                const next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                listEl.insertBefore(draggedItem, next ? targetItem.nextSibling : targetItem);
            }
        });

        listEl.addEventListener('dragend', () => {
            if (draggedItem) draggedItem.classList.remove('opacity-50');
            finalizeDragOrder(listEl);
        });

        // --- Mobile: Touch Events ---
        let touchDragItem = null;
        let touchClone = null;
        let touchStartY = 0;

        listEl.addEventListener('touchstart', (e) => {
            const handle = e.target.closest('.drag-handle');
            if (!handle) return;

            const li = handle.closest('li');
            if (!li) return;

            touchDragItem = li;
            touchStartY = e.touches[0].clientY;

            // 시각 피드백
            touchDragItem.classList.add('opacity-50');
            touchDragItem.style.transition = 'none';
        }, { passive: true });

        listEl.addEventListener('touchmove', (e) => {
            if (!touchDragItem) return;
            e.preventDefault();

            const touchY = e.touches[0].clientY;
            const targetEl = document.elementFromPoint(e.touches[0].clientX, touchY);
            if (!targetEl) return;

            const targetItem = targetEl.closest('li');
            if (targetItem && targetItem !== touchDragItem && listEl.contains(targetItem)) {
                const rect = targetItem.getBoundingClientRect();
                const next = (touchY - rect.top) / (rect.bottom - rect.top) > 0.5;
                listEl.insertBefore(touchDragItem, next ? targetItem.nextSibling : targetItem);
            }
        }, { passive: false });

        listEl.addEventListener('touchend', () => {
            if (!touchDragItem) return;
            touchDragItem.classList.remove('opacity-50');
            touchDragItem.style.transition = '';
            finalizeDragOrder(listEl);
            touchDragItem = null;
        });

        // 공통: 드래그 완료 후 데이터 순서 반영
        function finalizeDragOrder(list) {
            const newOrder = Array.from(list.children).map(li => parseInt(li.dataset.idx, 10));
            const reorderedProjects = newOrder.map(idx => data.projects[idx]);
            data.projects = reorderedProjects;
            renderApp();
            syncDataToAdmin();
        }
    }

    // 키보드 이벤트 (Ctrl + M)
    const ADMIN_PASS = window.viJoonEnv ? window.viJoonEnv.ADMIN_PASS : '';
    let isAdminAuthenticated = false;

    window.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key.toLowerCase() === 'm') {
            e.preventDefault();
            if (isAdminOpen) {
                closeAdminPanel();
            } else if (isAdminAuthenticated) {
                initAdminPanel();
            } else {
                const input = prompt('관리자 비밀번호를 입력하세요:');
                if (input === ADMIN_PASS) {
                    isAdminAuthenticated = true;
                    initAdminPanel();
                } else if (input !== null) {
                    alert('비밀번호가 올바르지 않습니다.');
                }
            }
        }
    });

    // ==========================================
    // AI Chatbot Logic
    // ==========================================
    function initChatbot() {
        const apiKey = window.viJoonEnv ? window.viJoonEnv.GEMINI_API_KEY : null;
        // 대화 히스토리 (멀티턴 지원)
        const chatHistory = [];

        const chatHTML = `
            <div id="vi-chatbot" class="fixed bottom-6 right-6 z-40 flex flex-col items-end pointer-events-none">
                <!-- Chat Window -->
                <div id="chat-window" class="hidden pointer-events-auto w-80 max-h-96 bg-gray-900 border border-brand-purple/50 rounded-2xl shadow-[0_4px_30px_rgba(138,43,226,0.3)] mb-4 flex-col overflow-hidden transition-all-300 transform origin-bottom-right">
                    <!-- Header -->
                    <div class="bg-gray-800 p-3 flex justify-between items-center border-b border-gray-700">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-brand-purple shadow-[0_0_8px_#8A2BE2] animate-pulse"></span>
                            <h3 class="font-bold text-white text-sm">vi.joon AI</h3>
                        </div>
                        <button id="close-chat" class="text-gray-400 hover:text-white">&times;</button>
                    </div>
                    <!-- Messages -->
                    <div id="chat-messages" class="flex-1 p-3 overflow-y-auto space-y-3 text-sm flex flex-col items-start bg-gray-900/50 min-h-[250px] max-h-[350px]">
                        <div class="bg-gray-800 text-gray-200 px-3 py-2 rounded-2xl rounded-tl-sm max-w-[85%]">
                            안녕하세요! 제 포트폴리오에 오신 것을 환영합니다. 프로젝트들에 대해 궁금한 점이 있다면 무엇이든 물어보세요! ✨
                        </div>
                    </div>
                    <!-- Input -->
                    <div class="p-2 bg-gray-800 border-t border-gray-700 flex gap-2">
                        <input type="text" id="chat-input" class="flex-1 bg-gray-900 border border-gray-700 rounded-full px-3 py-1.5 text-sm text-white focus:outline-none focus:border-brand-purple" placeholder="메시지 입력..." autocomplete="off">
                        <button id="send-chat" class="bg-brand-purple hover:bg-purple-600 text-white rounded-full p-2 w-8 h-8 flex items-center justify-center transition shadow-[0_0_8px_rgba(138,43,226,0.4)]">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                        </button>
                    </div>
                </div>
                
                <!-- Floating Button -->
                <button id="toggle-chat" class="pointer-events-auto w-14 h-14 bg-gradient-to-r from-purple-600 to-indigo-600 rounded-full shadow-[0_0_15px_rgba(138,43,226,0.6)] flex items-center justify-center hover-neon transition-all-300 transform hover:scale-105 active:scale-95 text-white text-2xl group">
                    <svg class="w-7 h-7 group-hover:animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                </button>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', chatHTML);

        const toggleBtn = document.getElementById('toggle-chat');
        const chatWindow = document.getElementById('chat-window');
        const closeBtn = document.getElementById('close-chat');
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-chat');
        const messagesDiv = document.getElementById('chat-messages');

        toggleBtn.addEventListener('click', () => {
            chatWindow.classList.toggle('hidden');
            chatWindow.classList.toggle('flex');
            if (!chatWindow.classList.contains('hidden')) chatInput.focus();
        });

        closeBtn.addEventListener('click', () => {
            chatWindow.classList.add('hidden');
            chatWindow.classList.remove('flex');
        });

        async function handleSend() {
            const text = chatInput.value.trim();
            if (!text) return;

            appendMessage(text, 'user');
            chatHistory.push({ role: 'user', text: text });
            chatInput.value = '';

            if (!apiKey) {
                appendMessage(".env.js 파일에 Gemini API Key를 먼저 설정해주세요.", 'system');
                return;
            }

            const typingId = appendMessage("답변을 생성중입니다...", 'ai', true);

            try {
                const response = await askGemini(text, apiKey, data, chatHistory);
                document.getElementById(typingId).remove();
                appendMessage(response, 'ai');
                chatHistory.push({ role: 'model', text: response });
            } catch (e) {
                document.getElementById(typingId).remove();
                appendMessage("오류가 발생했습니다: " + e.message, 'system');
            }
        }

        sendBtn.addEventListener('click', handleSend);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSend();
        });

        function appendMessage(msg, type, isTyping = false) {
            const div = document.createElement('div');
            const id = 'msg-' + Date.now();
            div.id = id;
            if (type === 'user') {
                div.className = "bg-brand-purple text-white px-3 py-2 rounded-2xl rounded-tr-sm max-w-[85%] self-end break-words";
            } else if (type === 'ai') {
                div.className = "bg-gray-800 text-gray-200 px-3 py-2 rounded-2xl rounded-tl-sm max-w-[85%] self-start break-words whitespace-pre-wrap" + (isTyping ? " animate-pulse text-gray-400" : "");
            } else {
                div.className = "bg-red-900/50 text-red-200 px-3 py-2 rounded-2xl text-xs max-w-[85%] self-center text-center break-words mt-2 mb-2";
            }
            div.textContent = msg;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return id;
        }
    }

    async function askGemini(question, apiKey, contextData, history) {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=${apiKey}`;

        const safeData = {
            profile: contextData.profile,
            projects: contextData.projects
        };

        const systemPrompt = `당신은 '${safeData.profile.title}'의 개인 프로젝트를 안내하는 큐레이터이자 친절한 AI 어시스턴트입니다.
다음 포트폴리오 데이터를 바탕으로 사용자의 질문에 한국어로 대답해주세요. 대답은 기술적이되 전문적이고 친근한 톤을 유지하고, 3~4문장 정도로 간결하게 답변해주세요. 정보를 나열하기보다는 자연스러운 대화체로 말해주세요.
데이터: ${JSON.stringify(safeData)}`;

        // 대화 히스토리를 Gemini contents 형식으로 변환
        const contents = [];

        // 첫 메시지에 시스템 프롬프트를 포함
        const previousMessages = history.slice(0, -1); // 현재 질문 제외 (이미 history에 push됨)
        if (previousMessages.length === 0) {
            // 첫 대화: 시스템 프롬프트 + 질문을 하나로
            contents.push({ role: 'user', parts: [{ text: systemPrompt + '\n\n사용자 질문: ' + question }] });
        } else {
            // 멀티턴: 첫 메시지에 시스템 프롬프트 포함, 이후 히스토리 추가
            previousMessages.forEach((msg, i) => {
                if (i === 0) {
                    contents.push({ role: 'user', parts: [{ text: systemPrompt + '\n\n사용자 질문: ' + msg.text }] });
                } else {
                    contents.push({ role: msg.role, parts: [{ text: msg.text }] });
                }
            });
            // 현재 질문 추가
            contents.push({ role: 'user', parts: [{ text: question }] });
        }

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents })
        });
        const json = await res.json();
        if (json.error) throw new Error(json.error.message);
        return json.candidates[0].content.parts[0].text;
    }

    // Init Chatbot
    initChatbot();

});
