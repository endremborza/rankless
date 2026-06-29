<svelte:head>
	<title>Privacy — Rankless</title>
	<meta
		name="description"
		content="What Rankless stores when you sign in with ORCID, and how we handle your data."
	/>
</svelte:head>

<section>
	<div class="prose">
		<h1>Privacy</h1>
		<p class="updated">Last updated 28 June 2026</p>

		<p>
			Rankless builds scholarly profiles from open data published by
			<a href="https://openalex.org/" target="_blank" rel="noopener">OpenAlex</a>. We show
			information that is already public. We do not run advertising, we do not use third-party
			trackers or analytics, and we never sell your data.
		</p>

		<h2>Who we are</h2>
		<p>
			Rankless is operated by the
			<a href="https://centerforcollectivelearning.org/" target="_blank" rel="noopener"
				>Center for Collective Learning</a
			>
			(CCL) at Corvinus University of Budapest. CCL is the data controller for the purposes of the EU
			General Data Protection Regulation (GDPR). You can reach us at rankless@&#8203;centerforcollectivelearning.org.
		</p>

		<h2>Signing in with ORCID</h2>
		<p>
			Logging in is optional, and only needed if you want to take ownership of a profile. We use
			ORCID's <code>/authenticate</code> scope — the minimum that confirms who you are. From ORCID
			we receive and store only your <strong>ORCID iD</strong> and <strong>name</strong>. We do not
			request or store your email, your ORCID password, or any other part of your ORCID record, and
			we keep no ORCID access or refresh tokens.
		</p>
		<p>When you sign in, this information is used to:</p>
		<ul>
			<li>
				keep you logged in, via a session cookie that holds your ORCID iD and name and expires after
				one day;
			</li>
			<li>record that your ORCID iD has signed in, so we can link you to the profile you own;</li>
			<li>attribute the corrections you make to your name on the public ledger described below.</li>
		</ul>
		<p>
			The legal basis for this processing is performance of the service you ask for when you choose
			to sign in (GDPR Art. 6(1)(b)).
		</p>

		<h2>The public ledger</h2>
		<p>
			Edits you make to a profile — adding a missing paper, removing one that isn't yours, merging
			duplicates — are written to a <strong>public, revocable ledger</strong> alongside your ORCID iD.
			This is deliberate: corrections are transparent and attributable. You can revoke any edit at any
			time from your profile, which removes it from the active record.
		</p>

		<h2>The optional survey</h2>
		<p>
			We sometimes show a short, optional survey. If you choose to answer it, we store your
			responses; if you are signed in, your ORCID iD is stored with them so we can understand who
			our users are. We do not log your IP address. Answering or dismissing the survey sets a cookie
			so we don't ask again. The legal basis is our legitimate interest in improving Rankless (GDPR
			Art. 6(1)(f)).
		</p>

		<h2>Cookies</h2>
		<ul>
			<li>
				<strong>session</strong> — strictly necessary; keeps you logged in for one day. Set only after
				you sign in.
			</li>
			<li>
				<strong>survey preference cookies</strong> — remember that you answered or dismissed the survey,
				so it isn't shown repeatedly.
			</li>
		</ul>
		<p>
			We use no advertising, tracking, or analytics cookies, so there is nothing to consent to
			beyond these functional cookies.
		</p>

		<h2>Retention</h2>
		<ul>
			<li>The session cookie expires after one day.</li>
			<li>Ledger edits are kept until you revoke them.</li>
			<li>
				The record that your ORCID iD signed in, and any survey responses, are kept until you ask us
				to delete them.
			</li>
		</ul>

		<h2>Your rights</h2>
		<p>
			Under the GDPR you have the right to access, correct, or delete the data we hold about you,
			and to object to or restrict its processing. You can revoke ledger edits yourself from your
			profile. For anything else — including deletion of your sign-in record or survey responses —
			email us at rankless@&#8203;centerforcollectivelearning.org and we will action it. You also
			have the right to lodge a complaint with the Hungarian data protection authority (NAIH).
		</p>
	</div>
</section>

<style>
	section {
		padding: 56px 0;
	}

	.prose {
		max-width: 760px;
		margin: 0 auto;
		padding: 0 var(--unified-margin, 16px);
		line-height: var(--lh-body);
	}

	.prose h1 {
		font-size: 2.6rem;
		margin: 0 0 6px 0;
		letter-spacing: -0.01em;
	}

	.prose h2 {
		font-size: 24px;
		letter-spacing: -0.01em;
		margin: 32px 0 8px 0;
	}

	.prose p,
	.prose li {
		font-size: var(--text-base);
	}

	.prose ul {
		padding-left: 20px;
	}

	.prose li {
		margin: 4px 0;
	}

	.updated {
		opacity: 0.6;
		font-size: var(--text-sm);
		margin-top: 0;
	}

	.prose code {
		font-size: 0.9em;
		padding: 1px 5px;
		background: rgba(var(--color-range-30), 0.12);
		border-radius: 3px;
	}
</style>
