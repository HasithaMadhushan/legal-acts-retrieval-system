import { RoleGuard } from "@/components/role-guard";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function AdminUploadPage() {
  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts/upload">
      <div className="mx-auto flex w-full max-w-[820px] flex-col gap-5">
        <section>
          <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Upload Act PDF</h1>
          <p className="mt-2 text-[14.5px] text-muted-foreground">
            English-language Sri Lankan Legal Act PDFs only, up to 50 MB. Duplicates are detected by file hash.
          </p>
        </section>
        <UploadDropzone />
      </div>
    </RoleGuard>
  );
}
