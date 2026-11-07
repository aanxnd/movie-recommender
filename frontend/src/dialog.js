export function containDialogFocus(event) {
  if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey)
    return
  const controls = [
    ...event.currentTarget.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((element) => element.getClientRects().length)
  const first = controls[0],
    last = controls.at(-1)
  if (
    first &&
    ((!event.shiftKey && document.activeElement === last) ||
      (event.shiftKey && document.activeElement === first))
  ) {
    event.preventDefault()
    const target = event.shiftKey ? last : first
    target.focus()
  }
}
