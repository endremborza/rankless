export async function copyToClipboard(text: string): Promise<void> {
	try {
		await navigator.clipboard.writeText(text);
		alert('Copied to clipboard');
	} catch (err) {
		console.error('Clipboard copy failed:', err);
		alert('Failed to copy text');
	}
}

export function downloadTextFile(filename: string, text: string): void {
	const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}
