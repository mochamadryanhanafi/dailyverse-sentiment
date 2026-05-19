<script>
  export let status = 'loading'
  export let label = ''

  $: badgeClass = status === 'ok' ? 'badge-success' :
                  status === 'error' ? 'badge-error' : 'badge-pending'
  $: dot = status === 'ok' ? 'bg-emerald-500' :
           status === 'error' ? 'bg-red-500' : 'bg-amber-500 animate-pulse'
  $: text = status === 'ok' ? 'Online' :
            status === 'error' ? 'Offline' : 'Checking…'
</script>

<span class={badgeClass}>
  <span class="w-1.5 h-1.5 rounded-full {dot}"></span>
  {label ? `${label}: ` : ''}{text}
</span>
