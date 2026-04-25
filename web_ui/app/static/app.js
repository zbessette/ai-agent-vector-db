// Web UI Alpine.js + HTMX glue.

function toast(message, type = 'error') {
  const bg = type === 'error' ? '#dc2626' : type === 'success' ? '#16a34a' : '#2563eb';
  Toastify({
    text: message,
    duration: type === 'error' ? 6000 : 3000,
    gravity: 'top',
    position: 'right',
    style: { background: bg },
    close: true,
  }).showToast();
}

async function apiError(r, fallback) {
  const body = await r.json().catch(() => ({}));
  toast(body.error || body.detail || fallback);
}

window.openEditEntry = async (ns, id) => {
  const r = await fetch(`/namespaces/${ns}/entries/${id}/edit`);
  if (!r.ok) { await apiError(r, 'Could not load entry editor'); return; }
  const html = await r.text();
  const root = document.querySelector('[x-data*="editingId"]');
  if (!root) return;
  const data = Alpine.$data(root);
  data.editingHtml = html;
  data.editingId = id;
};

window.deleteEntry = async (ns, id) => {
  if (!confirm("Delete this entry?")) return;
  const r = await fetch(`/api/namespaces/${ns}/entries/${id}`, {method: 'DELETE'});
  if (r.ok) window.location.reload();
  else await apiError(r, 'Delete failed');
};

// Namespace lifecycle helpers (used from namespace_detail.html Config tab).

window.activateNamespace = async (name) => {
  if (!confirm(`Activate namespace ${name}?`)) return;
  const r = await fetch(`/api/namespaces/${name}/confirm`, {method: 'POST'});
  if (r.ok) location.reload();
  else await apiError(r, 'Activate failed');
};

window.reindexNamespace = async (name) => {
  if (!confirm('Reindex all entries?')) return;
  const r = await fetch(`/api/namespaces/${name}/reindex`, {method: 'POST'});
  if (r.ok) location.reload();
  else await apiError(r, 'Reindex failed');
};

window.deleteNamespace = async (name) => {
  if (!confirm(`Delete namespace ${name}? This cannot be undone.`)) return;
  const r = await fetch(`/api/namespaces/${name}`, {method: 'DELETE'});
  if (r.ok) location.href = '/namespaces';
  else await apiError(r, 'Delete failed');
};

window.updateNamespace = async (name, formEl) => {
  const r = await fetch(`/api/namespaces/${name}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.fromEntries(new FormData(formEl))),
  });
  if (r.ok) location.reload();
  else await apiError(r, 'Update failed');
};
