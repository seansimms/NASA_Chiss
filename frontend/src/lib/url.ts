export function getQuery(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

export function setQuery(updates: Record<string, string|undefined>) {
  const qs = getQuery();
  for (const [k,v] of Object.entries(updates)) {
    if (v === undefined || v === null || v === "") qs.delete(k);
    else qs.set(k, String(v));
  }
  const url = `${window.location.pathname}?${qs.toString()}${window.location.hash || ""}`;
  window.history.pushState({}, "", url);
}

export function getParam(name: string): string | undefined {
  const v = getQuery().get(name);
  return v === null ? undefined : v;
}

export function scrollToTab(tab: string) {
  const id = tab.toLowerCase();
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({behavior:"smooth", block:"start"});
}


