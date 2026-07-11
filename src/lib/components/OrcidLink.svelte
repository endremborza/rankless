<script lang="ts">
	export let orcid: string;
</script>

<a class="orcid" href="https://orcid.org/{orcid}" target="_blank" rel="noopener">{orcid}</a>

<style>
	.orcid {
		font-family: monospace;
		font-size: 0.8rem;
		white-space: nowrap;
	}
</style>
