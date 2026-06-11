"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "../lib/api";

export default function Nav() {
  const [authed, setAuthed] = useState(false);
  useEffect(() => { setAuthed(!!getToken()); }, []);

  return (
    <nav className="nav">
      <span className="brand">
        <span className="dot" />
        Apply&nbsp;Co-Pilot
      </span>
      <span className="status">
        <span className="pulse" />
        co-pilot engaged
      </span>
      <span className="links">
        <Link href="/">Dashboard</Link>
        <Link href="/profile">Profile</Link>
        <Link href="/jobs">Jobs</Link>
        <Link href="/applications">Applications</Link>
        {authed ? <Link href="/settings">Settings</Link> : <Link href="/login">Sign in</Link>}
      </span>
    </nav>
  );
}
