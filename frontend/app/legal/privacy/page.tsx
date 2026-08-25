export default function PrivacyPolicyPage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="font-serif text-4xl font-semibold">Privacy Policy</h1>
      <p className="text-sm text-muted-foreground">Last updated: 23 August 2026</p>
      <p>
        LexAtlas collects only what is needed to run accounts, retrieval, and administrator
        review. We do not sell personal data.
      </p>
      <h2 className="font-serif text-2xl">Data we collect</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>Name and email address for your account</li>
        <li>Role, attorney verification files, and administrator review notes</li>
        <li>Reading history and saved items you create while signed in</li>
        <li>Uploaded Act PDFs and derived text, sections, and citations</li>
        <li>Technical logs needed to operate and secure the service</li>
      </ul>
      <h2 className="font-serif text-2xl">Storage and retention</h2>
      <p>
        Data is stored on the application database and configured file storage. Academic
        deployments retain records while the project is active unless an administrator deletes
        them earlier. Password reset tokens expire automatically.
      </p>
      <h2 className="font-serif text-2xl">Your rights</h2>
      <p>
        You may request correction or deletion of your account data from an administrator.
        Deleting an account removes saved items and reading history tied to that user. Act
        records uploaded for the corpus may be retained as research material.
      </p>
    </article>
  );
}
