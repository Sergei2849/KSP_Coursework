const USER_KEY = 'engineCourseworkUser';
const STATUSES = ['Новая', 'В диагностике', 'Ожидает деталь', 'Выполнена', 'Отменена'];

let cachedEngines = [];
let cachedRequests = [];

document.addEventListener('DOMContentLoaded', function () {
    renderAuthState();
    initLoginPage();
    initEnginesPage();
    initPartsPage();
    initRequestsPage();
    initStatsPage();
    initLogsPage();
});

function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) {
        return null;
    }
    try {
        return JSON.parse(raw);
    } catch (error) {
        localStorage.removeItem(USER_KEY);
        return null;
    }
}

function setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function logout() {
    localStorage.removeItem(USER_KEY);
    window.location.href = 'login.html';
}

function isAdmin() {
    const user = getUser();
    return user && user.role === 'admin';
}

function authHeaders() {
    const user = getUser();
    const headers = {'Content-Type': 'application/json'};
    if (user) {
        headers['X-User-Id'] = user.id;
    }
    return headers;
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: {
            ...authHeaders(),
            ...(options.headers || {})
        }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || 'Ошибка запроса');
    }
    return data;
}

function renderAuthState() {
    const user = getUser();
    document.querySelectorAll('[data-admin]').forEach((node) => {
        node.classList.toggle('hidden', !isAdmin());
    });
    document.querySelectorAll('[data-staff]').forEach((node) => {
        const user = getUser();
        node.classList.toggle('hidden', !(user && ['admin', 'mechanic'].includes(user.role)));
    });

    document.querySelectorAll('nav').forEach((nav) => {
        const label = document.createElement('span');
        label.className = 'user-label';
        label.textContent = user ? `${user.name} (${user.role_name})` : 'Вход не выполнен';
        nav.appendChild(label);
    });

    const currentUserLabel = document.getElementById('currentUserLabel');
    if (currentUserLabel) {
        currentUserLabel.textContent = user
            ? `Сейчас выполнен вход: ${user.name}, ${user.email}, роль: ${user.role_name}`
            : 'Вход не выполнен';
    }
}

function showMessage(idOrNode, text, isError = false) {
    const node = typeof idOrNode === 'string' ? document.getElementById(idOrNode) : idOrNode;
    if (!node) {
        return;
    }
    node.textContent = text;
    node.classList.toggle('error', isError);
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function requireLoggedIn(messageId) {
    if (getUser()) {
        return true;
    }
    showMessage(messageId, 'Сначала выполните вход.', true);
    return false;
}

function initLoginPage() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const logoutButton = document.getElementById('logoutButton');

    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const email = loginForm.email.value.trim();
            const password = loginForm.password.value;

            if (!isValidEmail(email)) {
                showMessage('loginMessage', 'Введите корректный email.', true);
                return;
            }

            try {
                const user = await api('/api/auth/login', {
                    method: 'POST',
                    body: JSON.stringify({email, password})
                });
                setUser(user);
                showMessage('loginMessage', 'Вход выполнен.');
                setTimeout(() => window.location.href = 'index.html', 400);
            } catch (error) {
                showMessage('loginMessage', error.message, true);
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const payload = {
                name: registerForm.name.value.trim(),
                email: registerForm.email.value.trim(),
                password: registerForm.password.value
            };

            if (!isValidEmail(payload.email)) {
                showMessage('registerMessage', 'Введите корректный email.', true);
                return;
            }

            try {
                const user = await api('/api/auth/register', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                setUser(user);
                showMessage('registerMessage', 'Регистрация выполнена.');
                setTimeout(() => window.location.href = 'index.html', 400);
            } catch (error) {
                showMessage('registerMessage', error.message, true);
            }
        });
    }
}

async function loadEngines() {
    cachedEngines = await api('/api/engines');
    return cachedEngines;
}

function fillEngineSelect(select) {
    select.innerHTML = cachedEngines.map((engine) => (
        `<option value="${engine.id}">${escapeHtml(engine.model)} (${escapeHtml(engine.serial_number || 'без номера')})</option>`
    )).join('');
}

function initEnginesPage() {
    const form = document.getElementById('engineForm');
    const table = document.getElementById('enginesTable');
    const refresh = document.getElementById('refreshEngines');
    if (!table) {
        return;
    }

    const render = async function () {
        if (!requireLoggedIn('engineMessage')) {
            table.innerHTML = '<tr><td colspan="6">Войдите в систему</td></tr>';
            return;
        }
        try {
            const engines = await loadEngines();
            table.innerHTML = engines.map((engine) => `
                <tr>
                    <td>${escapeHtml(engine.model)}</td>
                    <td>${escapeHtml(engine.engine_type)}</td>
                    <td>${engine.power_hp || '-'}</td>
                    <td>${engine.volume_liters || '-'}</td>
                    <td>${escapeHtml(engine.serial_number || '-')}</td>
                    <td>${escapeHtml(engine.owner_name)}</td>
                </tr>
            `).join('') || '<tr><td colspan="6">Двигателей пока нет</td></tr>';
        } catch (error) {
            showMessage('engineMessage', error.message, true);
        }
    };

    if (refresh) {
        refresh.addEventListener('click', render);
    }

    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            if (!requireLoggedIn('engineMessage')) {
                return;
            }
            const payload = Object.fromEntries(new FormData(form).entries());
            try {
                await api('/api/engines', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                form.reset();
                showMessage('engineMessage', 'Двигатель добавлен.');
                await render();
            } catch (error) {
                showMessage('engineMessage', error.message, true);
            }
        });
    }

    render();
}

function initPartsPage() {
    const form = document.getElementById('partForm');
    const table = document.getElementById('partsTable');
    const search = document.getElementById('partSearch');
    if (!table) {
        return;
    }

    const render = async function () {
        if (!requireLoggedIn('partMessage')) {
            table.innerHTML = '<tr><td colspan="5">Войдите в систему</td></tr>';
            return;
        }
        try {
            await loadEngines();
            if (form) {
                fillEngineSelect(form.engine_id);
            }
            const query = search ? search.value.trim() : '';
            const parts = await api(`/api/parts${query ? `?q=${encodeURIComponent(query)}` : ''}`);
            table.innerHTML = parts.map((part) => `
                <tr>
                    <td>${escapeHtml(part.name)}</td>
                    <td>${escapeHtml(part.part_code || '-')}</td>
                    <td>${escapeHtml(part.engine_model)}</td>
                    <td>${escapeHtml(part.condition)}</td>
                    <td>${escapeHtml(part.note || '-')}</td>
                </tr>
            `).join('') || '<tr><td colspan="5">Деталей пока нет</td></tr>';
        } catch (error) {
            showMessage('partMessage', error.message, true);
        }
    };

    if (search) {
        search.addEventListener('input', render);
    }

    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            if (!requireLoggedIn('partMessage')) {
                return;
            }
            const payload = Object.fromEntries(new FormData(form).entries());
            try {
                await api('/api/parts', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                form.reset();
                showMessage('partMessage', 'Деталь добавлена.');
                await render();
            } catch (error) {
                showMessage('partMessage', error.message, true);
            }
        });
    }

    render();
}

function initRequestsPage() {
    const form = document.getElementById('requestForm');
    const table = document.getElementById('requestsTable');
    const exportButton = document.getElementById('exportRequests');
    if (!table) {
        return;
    }

    const render = async function () {
        if (!requireLoggedIn('requestMessage')) {
            table.innerHTML = '<tr><td colspan="7">Войдите в систему</td></tr>';
            return;
        }
        try {
            await loadEngines();
            if (form) {
                fillEngineSelect(form.engine_id);
            }
            cachedRequests = await api('/api/service-requests');
            table.innerHTML = cachedRequests.map((request) => `
                <tr>
                    <td>${request.id}</td>
                    <td>${escapeHtml(request.engine_model)}</td>
                    <td>${escapeHtml(request.client_name)}</td>
                    <td>${escapeHtml(request.problem)}</td>
                    <td>${escapeHtml(request.priority)}</td>
                    <td><span class="status">${escapeHtml(request.status)}</span></td>
                    <td data-admin>${renderStatusControl(request)}</td>
                </tr>
            `).join('') || '<tr><td colspan="7">Заявок пока нет</td></tr>';
            document.querySelectorAll('[data-admin]').forEach((node) => node.classList.toggle('hidden', !isAdmin()));
        } catch (error) {
            showMessage('requestMessage', error.message, true);
        }
    };

    if (form) {
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            if (!requireLoggedIn('requestMessage')) {
                return;
            }
            const payload = Object.fromEntries(new FormData(form).entries());
            try {
                await api('/api/service-requests', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                form.reset();
                showMessage('requestMessage', 'Заявка создана.');
                await render();
            } catch (error) {
                showMessage('requestMessage', error.message, true);
            }
        });
    }

    table.addEventListener('change', async function (event) {
        if (!event.target.matches('[data-status-id]')) {
            return;
        }
        try {
            await api(`/api/service-requests/${event.target.dataset.statusId}`, {
                method: 'PATCH',
                body: JSON.stringify({status: event.target.value, admin_comment: 'Статус изменен администратором'})
            });
            showMessage('requestMessage', 'Статус обновлен.');
            await render();
        } catch (error) {
            showMessage('requestMessage', error.message, true);
        }
    });

    if (exportButton) {
        exportButton.addEventListener('click', exportRequestsCsv);
    }

    render();
}

function renderStatusControl(request) {
    return `<select data-status-id="${request.id}">
        ${STATUSES.map((status) => `<option ${status === request.status ? 'selected' : ''}>${status}</option>`).join('')}
    </select>`;
}

function exportRequestsCsv() {
    const rows = [['id', 'engine', 'client', 'problem', 'priority', 'status']];
    cachedRequests.forEach((request) => {
        rows.push([request.id, request.engine_model, request.client_name, request.problem, request.priority, request.status]);
    });
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(';')).join('\n');
    const blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'service_requests.csv';
    link.click();
    URL.revokeObjectURL(url);
}

function initLogsPage() {
    const list = document.getElementById('logsList');
    const refresh = document.getElementById('refreshLogs');
    if (!list) {
        return;
    }

    const render = async function () {
        if (!isAdmin()) {
            list.innerHTML = '<li>Журнал доступен только администратору.</li>';
            return;
        }
        try {
            const logs = await api('/api/logs');
            list.innerHTML = logs.map((line) => `<li>${escapeHtml(line)}</li>`).join('') || '<li>Логов пока нет</li>';
        } catch (error) {
            list.innerHTML = `<li>${escapeHtml(error.message)}</li>`;
        }
    };

    if (refresh) {
        refresh.addEventListener('click', render);
    }
    render();
}

function initStatsPage() {
    const cards = document.getElementById('statsCards');
    const refresh = document.getElementById('refreshStats');
    if (!cards) {
        return;
    }

    const statusTable = document.getElementById('statusStatsTable');
    const engineTable = document.getElementById('engineStatsTable');
    const actionsList = document.getElementById('recentActionsList');

    const render = async function () {
        const user = getUser();
        if (!user || !['admin', 'mechanic'].includes(user.role)) {
            showMessage('statsMessage', 'Статистика доступна администратору и механику.', true);
            return;
        }

        try {
            const stats = await api('/api/stats');
            const labels = {
                engines: 'Двигатели',
                parts: 'Детали',
                requests: 'Заявки',
                users: 'Пользователи'
            };
            cards.innerHTML = Object.entries(stats.totals).map(([key, value]) => `
                <article class="stat-card">
                    <strong>${value}</strong>
                    <span>${labels[key]}</span>
                </article>
            `).join('');

            statusTable.innerHTML = stats.statuses.map((row) => `
                <tr>
                    <td>${escapeHtml(row.status)}</td>
                    <td>${row.requests_count}</td>
                </tr>
            `).join('') || '<tr><td colspan="2">Заявок пока нет</td></tr>';

            engineTable.innerHTML = stats.engines.map((engine) => `
                <tr>
                    <td>${escapeHtml(engine.model)}<br><span class="muted">${escapeHtml(engine.serial_number || '-')}</span></td>
                    <td>${engine.parts_count}</td>
                    <td>${engine.requests_count}</td>
                </tr>
            `).join('') || '<tr><td colspan="3">Двигателей пока нет</td></tr>';

            actionsList.innerHTML = stats.recent_actions.map((action) => `
                <li>${escapeHtml(action.created_at)} | ${escapeHtml(action.user_name || 'system')} | ${escapeHtml(action.action)} | ${escapeHtml(action.details || '')}</li>
            `).join('') || '<li>Действий пока нет</li>';
            showMessage('statsMessage', 'Статистика обновлена.');
        } catch (error) {
            showMessage('statsMessage', error.message, true);
        }
    };

    if (refresh) {
        refresh.addEventListener('click', render);
    }
    render();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}
