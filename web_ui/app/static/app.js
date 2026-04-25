// Web UI Alpine.js + HTMX glue.

document.addEventListener('alpine:init', () => {
  // Sync Alpine state with native <dialog> elements on namespace detail page.
  Alpine.effect(() => {
    const root = document.querySelector('[x-data*="openNew"]');
    if (!root) return;
    const data = root._x_dataStack ? root._x_dataStack[0] : null;
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
  const data = root._x_dataStack[0];
  data.editingHtml = html;
  data.editingId = id;
};

window.deleteEntry = async (ns, id) => {
  if (!confirm("Delete this entry?")) return;
  const r = await fetch(`/api/namespaces/${ns}/entries/${id}`, {method: 'DELETE'});
  if (r.ok) window.location.reload();
  else alert("Delete failed");
};
