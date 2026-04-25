// Web UI Alpine.js + HTMX glue.

document.addEventListener('alpine:init', () => {
  // Sync Alpine state with native <dialog> elements on namespace detail page.
  Alpine.effect(() => {
    const root = document.querySelector('[x-data*="openNew"]');
    if (!root) return;
    const data = Alpine.$data(root);
    if (!data) return;
    const dialogs = root.querySelectorAll('dialog');
    const newDialog = dialogs[0];
    if (newDialog) {
      if (data.openNew && !newDialog.open) newDialog.showModal();
      if (!data.openNew && newDialog.open) newDialog.close();
    }
    const editDialog = dialogs[1];
    if (editDialog) {
      if (data.editingId && !editDialog.open) editDialog.showModal();
      if (!data.editingId && editDialog.open) editDialog.close();
    }
  });
});

window.openEditEntry = async (ns, id) => {
  const html = await fetch(`/namespaces/${ns}/entries/${id}/edit`).then(r => r.text());
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
  else alert("Delete failed");
};

// Namespace lifecycle helpers (used from namespace_detail.html Config tab).

window.activateNamespace = async (name) => {
  if (!confirm(`Activate namespace ${name}?`)) return;
  const r = await fetch(`/api/namespaces/${name}/confirm`, {method: 'POST'});
  if (r.ok) location.reload();
  else alert('Activate failed');
};

window.reindexNamespace = async (name) => {
  if (!confirm('Reindex all entries?')) return;
  const r = await fetch(`/api/namespaces/${name}/reindex`, {method: 'POST'});
  if (r.ok) location.reload();
  else {
    const body = await r.json().catch(() => ({}));
    alert(body.error || 'Reindex failed');
  }
};

window.deleteNamespace = async (name) => {
  if (!confirm(`Delete namespace ${name}? This cannot be undone.`)) return;
  const r = await fetch(`/api/namespaces/${name}`, {method: 'DELETE'});
  if (r.ok) location.href = '/namespaces';
  else alert('Delete failed');
};

window.updateNamespace = async (name, formEl) => {
  const r = await fetch(`/api/namespaces/${name}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.fromEntries(new FormData(formEl))),
  });
  if (r.ok) location.reload();
  else alert('Update failed');
};
