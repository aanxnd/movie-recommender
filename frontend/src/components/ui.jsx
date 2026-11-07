import { ArrowUpRight, Film, Star } from 'lucide-react'

export function Brand() {
  return (
    <span className="brand">
      movelle<span className="brand-stop">.</span>
    </span>
  )
}
export function SectionHeading({
  eyebrow,
  title,
  description,
  children,
  id,
  as: Heading = 'h2',
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <Heading id={id}>{title}</Heading>
        {description && <p className="section-description">{description}</p>}
      </div>
      {children}
    </div>
  )
}
export function EmptyState({ title, children, action, icon: Icon = Film }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={24} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <div>
        <h3>{title}</h3>
        <div className="empty-description">{children}</div>
        {action && <div className="empty-action">{action}</div>}
      </div>
    </div>
  )
}
export function Skeletons({ label = 'Finding recommendations…', count = 4 }) {
  return (
    <div role="status" aria-label={label} className="loading-state">
      <p className="loading-label">
        <span className="status-dot" />
        {label}
      </p>
      <div className="movie-grid skeleton-grid" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="skeleton-card" style={{ '--i': i }}>
            <div className="skeleton-cover" />
            <div className="skeleton-line" />
            <div className="skeleton-line short" />
          </div>
        ))}
      </div>
    </div>
  )
}
// Fractional fill adapted from shadcncraft's Star Rating via 21st MCP, demo 29309.
export function StarRating({ value, label }) {
  return (
    <span
      className="star-rating"
      role="img"
      aria-label={label || `${value} out of 5 stars`}
    >
      {Array.from({ length: 5 }, (_, index) => (
        <span className="rating-star" key={index} aria-hidden="true">
          <Star size={16} strokeWidth={1.4} />
          <span
            className="rating-star-fill"
            style={{
              width: `${Math.max(0, Math.min(1, value - index)) * 100}%`,
            }}
          >
            <Star size={16} fill="currentColor" strokeWidth={1.4} />
          </span>
        </span>
      ))}
    </span>
  )
}
export function TextLink({ children, ...props }) {
  return (
    <button type="button" className="text-link" {...props}>
      {children}
      <ArrowUpRight size={16} aria-hidden="true" />
    </button>
  )
}
