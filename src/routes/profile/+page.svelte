<script lang="ts">
  import { page } from '$app/stores';
</script>

{#if $page.data.user}
  <h1>Welcome, {$page.data.user.name}</h1>
  <p>Your ORCID iD: {$page.data.user.orcid}</p>
  <a href="/logout">Logout</a>
{:else}
  <h1>Not logged in</h1>
  <a href="/login">Login with ORCID</a>
{/if}

