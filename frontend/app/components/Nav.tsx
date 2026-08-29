import Link from "next/link";

export default function Nav() {
  return (
    <nav>
      <Link href="/">Dashboard</Link>
      <Link href="/jobs">Jobs</Link>
      <Link href="/approvals">Approvals</Link>
      <Link href="/applications">Applications</Link>
      <Link href="/profile">Profile</Link>
    </nav>
  );
}
