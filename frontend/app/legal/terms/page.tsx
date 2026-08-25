export default function TermsOfUsePage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="font-serif text-4xl font-semibold">Terms of Use</h1>
      <p className="text-sm text-muted-foreground">Last updated: 23 August 2026</p>
      <p>
        LexAtlas is an academic research prototype for retrieving Sri Lankan Legal Acts
        and mapped citations. It is a retrieval aid, not a law firm, not an official gazette,
        and not a substitute for professional legal services.
      </p>
      <h2 className="font-serif text-2xl">No legal advice</h2>
      <p>
        Content on this system is for information retrieval only. It does not constitute legal
        advice, a legal opinion, or an authoritative consolidation of the law. Always verify
        material against official sources and qualified professionals.
      </p>
      <h2 className="font-serif text-2xl">Accounts</h2>
      <p>
        You must provide accurate registration details, keep credentials confidential, and use
        the service only for lawful research and study. Attorney-at-Law access requires
        enrollment verification and administrator approval. Administrators may suspend accounts
        that abuse the service or upload infringing or harmful files.
      </p>
      <h2 className="font-serif text-2xl">Content accuracy</h2>
      <p>
        Extracted text, section splits, and citation mappings can contain errors. Unverified
        records may be incomplete. You are responsible for checking official publications before
        relying on any result.
      </p>
      <h2 className="font-serif text-2xl">Limitation of liability</h2>
      <p>
        The service is provided as-is for academic use. To the extent permitted by law, the
        operators are not liable for decisions, filings, or losses arising from use of retrieved
        material.
      </p>
    </article>
  );
}
