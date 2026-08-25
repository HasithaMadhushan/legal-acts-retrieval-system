"use client";

import { useEffect, useState } from "react";
import {
  approveLawyerRequest,
  deactivateUser,
  exportUrl,
  listUsers,
  rejectLawyerRequest,
  updateUser
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { User } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState("");

  function loadUsers() {
    listUsers()
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load users."));
  }

  useEffect(() => {
    loadUsers();
  }, []);

  const pendingLawyers = users.filter((user) => user.lawyer_request_status === "pending");

  async function review(userId: string, action: "approve" | "reject") {
    setError("");
    setPendingId(userId);
    try {
      if (action === "approve") {
        await approveLawyerRequest(userId);
      } else {
        await rejectLawyerRequest(userId);
      }
      loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update attorney request.");
    } finally {
      setPendingId("");
    }
  }

  async function changeRole(userId: string, role: User["role"]) {
    setError("");
    setPendingId(userId);
    try {
      await updateUser(userId, { role });
      loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the user role.");
    } finally {
      setPendingId("");
    }
  }

  async function deactivate(userId: string) {
    setError("");
    setPendingId(userId);
    try {
      await deactivateUser(userId);
      loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to deactivate the user.");
    } finally {
      setPendingId("");
    }
  }

  async function downloadProof(userId: string) {
    setError("");
    const token = getToken();
    if (!token) {
      setError("Sign in again to download enrollment proof.");
      return;
    }
    try {
      const response = await fetch(exportUrl(`/users/${userId}/enrollment-proof`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error("Unable to download enrollment proof.");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") ?? "";
      const match = /filename="?([^"]+)"?/i.exec(disposition);
      const filename = match?.[1] ?? `enrollment-proof-${userId}`;
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to download enrollment proof.");
    }
  }

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/users">
      <div className="flex flex-col gap-5">
        <div>
          <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Users</h1>
          <p className="mt-2 text-[14.5px] text-muted-foreground">
            Manage accounts, roles and attorney verification requests.
          </p>
        </div>
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">Attorney verification requests · {pendingLawyers.length}</p>
        <Card className="rounded-lg">
          <CardHeader>
            <CardTitle className="font-serif">Pending attorney requests</CardTitle>
            <CardDescription>
              Review enrollment proof, then approve to grant LAWYER access. Until then the account
              stays General User.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {pendingLawyers.length === 0 ? (
              <p className="text-sm text-muted-foreground">No pending attorney verification requests.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Enrollment</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingLawyers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>{user.full_name}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>{user.enrollment_number ?? "—"}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={() => downloadProof(user.id)}>
                            Download proof
                          </Button>
                          <Button
                            size="sm"
                            disabled={pendingId === user.id}
                            onClick={() => review(user.id, "approve")}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={pendingId === user.id}
                            onClick={() => review(user.id, "reject")}
                          >
                            Reject
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">All users · {users.length}</p>
        <Card className="rounded-lg">
          <CardHeader>
            <CardTitle>Users and roles</CardTitle>
            <CardDescription>All registered accounts in the academic prototype.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Attorney request</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>{user.full_name}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{user.role}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={user.lawyer_request_status === "pending" ? "default" : "outline"}>
                        {user.lawyer_request_status ?? "none"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={user.is_active ? "secondary" : "destructive"}>
                        {user.is_active ? "ACTIVE" : "INACTIVE"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex min-w-52 items-center gap-2">
                        <Select
                          value={user.role}
                          disabled={!user.is_active || user.role === "ADMIN" || pendingId === user.id}
                          onValueChange={(value) => void changeRole(user.id, value as User["role"])}
                        >
                          <SelectTrigger className="h-8 w-36" aria-label={`Role for ${user.email}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="GENERAL_USER">General user</SelectItem>
                            <SelectItem value="LAWYER">Lawyer</SelectItem>
                          </SelectContent>
                        </Select>
                        {user.role !== "ADMIN" && user.is_active ? (
                          <ConfirmDialog
                            title="Deactivate this account?"
                            description={`${user.email} will no longer be able to sign in.`}
                            triggerLabel="Deactivate"
                            confirmLabel="Deactivate"
                            pendingLabel="Deactivating..."
                            pending={pendingId === user.id}
                            onConfirm={() => deactivate(user.id)}
                          />
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </RoleGuard>
  );
}
