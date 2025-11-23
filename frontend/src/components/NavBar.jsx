import { NavLink } from "react-router-dom";
import LogoMark from "./LogoMark";

const links = [
  { href: "/", label: "Home" },
  { href: "/multiplayer", label: "Online" },
  { href: "/computer", label: "Vs Computer" },
  { href: "/replay", label: "Replay" },
  { href: "/analytics", label: "Analytics" },
  { href: "/settings", label: "Settings" },
  { href: "/auth", label: "Account" },
];

function NavBar() {
  return (
    <nav className="top-nav">
      <div className="brand">
        <LogoMark />
        <span>Chessica</span>
      </div>
      <div className="nav-links">
        {links.map((link) => (
          <NavLink
            key={link.href}
            to={link.href}
            className={({ isActive }) => (isActive ? "active" : "")}
            end={link.href === "/"}
          >
            {link.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default NavBar;
