import Link from 'next/link'

type BrandLogoProps = {
  href?: string
  className?: string
  compact?: boolean
}

export default function BrandLogo({ href = '/', className = '', compact = false }: BrandLogoProps) {
  return <Link href={href} className={`brand-logo ${compact ? 'brand-logo-compact' : ''} ${className}`} aria-label="Crafdeck home">
    <svg className="brand-logo-mark" viewBox="0 0 40 40" role="img" aria-label="Crafdeck mark">
      <rect width="40" height="40" rx="11" fill="#101828" />
      <rect x="9" y="8" width="22" height="24" rx="5" transform="rotate(-9 20 20)" fill="#FF5B2E" opacity=".55" />
      <rect x="9" y="8" width="22" height="24" rx="5" transform="rotate(9 20 20)" fill="#FF5B2E" opacity=".85" />
      <rect x="9" y="8" width="22" height="24" rx="5" fill="#fff" />
      <path d="M25 15.5A6 6 0 1 0 25 24.5" fill="none" stroke="#101828" strokeWidth="3.2" strokeLinecap="round" />
      <rect x="25.6" y="18.4" width="3.2" height="3.2" rx=".8" fill="#FF5B2E" />
    </svg>
    <span className="brand-logo-name">Crafdeck</span>
  </Link>
}
