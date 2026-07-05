"use client";

import { useEffect, useState } from "react";
import { listUsers } from "@/lib/api";
import type { User } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listUsers().then(setUsers).catch((err) => setError(err instanceof Error ? err.message : "Unable to load users."));
  }, []);

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/users">
      <div className="grid">
        <LegalDisclaimer />
        <section className="panel">
          <h1>Users and roles</h1>
          {error ? <p className="error">{error}</p> : null}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.full_name}</td>
                    <td>{user.email}</td>
                    <td><StatusBadge value={user.role} /></td>
                    <td><StatusBadge value={user.is_active ? "ACTIVE" : "INACTIVE"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </RoleGuard>
  );
}
