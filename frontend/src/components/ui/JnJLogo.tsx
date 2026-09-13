/**
 * J&J MedTech logo — inline SVG, always renders, no external dependency.
 * Uses the official J&J brand red (#eb1700) and the classic wordmark style.
 */

interface JnJLogoProps {
  height?: number;
  variant?: 'full' | 'icon';
}

export function JnJLogo({ height = 44, variant = 'full' }: JnJLogoProps) {
  if (variant === 'icon') {
    // Just the J&J red shield icon
    return (
      <svg
        height={height}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Johnson & Johnson"
        style={{ display: 'block', flexShrink: 0 }}
      >
        {/* Red background circle */}
        <circle cx="24" cy="24" r="24" fill="#eb1700" />
        {/* J&J white wordmark abbreviation */}
        <text
          x="24"
          y="32"
          textAnchor="middle"
          fill="white"
          fontFamily="Georgia, 'Times New Roman', serif"
          fontStyle="italic"
          fontSize="22"
          fontWeight="700"
          letterSpacing="-1"
        >
          J&amp;J
        </text>
      </svg>
    )
  }

  // Full wordmark with "JOHNSON & JOHNSON" and "MedTech" sub-label
  return (
    <svg
      height={height}
      viewBox="0 0 220 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Johnson & Johnson MedTech"
      style={{ display: 'block', flexShrink: 0 }}
    >
      {/* Red accent bar on left */}
      <rect x="0" y="0" width="5" height="48" rx="2" fill="#eb1700" />

      {/* J&J red circle icon */}
      <circle cx="28" cy="24" r="20" fill="#eb1700" />
      <text
        x="28"
        y="31"
        textAnchor="middle"
        fill="white"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontStyle="italic"
        fontSize="18"
        fontWeight="700"
        letterSpacing="-1"
      >
        J&amp;J
      </text>

      {/* JOHNSON & JOHNSON text */}
      <text
        x="56"
        y="22"
        fill="#1a1410"
        fontFamily="Inter, -apple-system, sans-serif"
        fontSize="13"
        fontWeight="800"
        letterSpacing="0.05em"
      >
        JOHNSON &amp; JOHNSON
      </text>
      {/* MedTech sub-label */}
      <text
        x="56"
        y="36"
        fill="#eb1700"
        fontFamily="Inter, -apple-system, sans-serif"
        fontSize="10"
        fontWeight="700"
        letterSpacing="0.15em"
      >
        MedTech
      </text>
    </svg>
  )
}
