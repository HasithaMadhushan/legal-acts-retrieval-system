import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function AdminUploadPage() {
  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts/upload">
      <div className="grid">
        <LegalDisclaimer />
        <section>
          <h1>Upload Legal Act PDF</h1>
          <p className="muted">Only Admin users can upload PDFs. Extracted data remains unverified until Admin review.</p>
        </section>
        <UploadDropzone />
      </div>
    </RoleGuard>
  );
}
