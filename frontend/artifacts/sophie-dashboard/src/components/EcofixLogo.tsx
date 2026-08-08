// The real Ecofix wordmark (fetched from ecofixgp.be's own asset CDN,
// https://framerusercontent.com/images/dOdrhUVN8xWnMhvRnxNpj0fFY.svg).
// The "Ecofix" text uses `currentColor` (was a hardcoded #fff in the
// original) so it reads correctly on both the dark sidebar and any future
// light-background placement; the zigzag mark keeps the brand's fixed teal
// (#42B3A2 - also this theme's --primary) since a logo mark shouldn't
// recolor with its surroundings.
export function EcofixLogo({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 98 37" fill="none" className={className}>
      <path
        fill="currentColor"
        d="M32 27.324V9.834h11.063v2.04h-8.815v5.048h7.916v2.04h-7.916v6.323h8.815v2.04zm18.722.256c-3.746 0-6.268-2.652-6.268-6.63s2.522-6.629 6.268-6.629c3.172 0 5.62 2.117 6.094 5.303h-1.898c-.375-2.116-2.048-3.518-4.196-3.518-2.547 0-4.27 1.938-4.27 4.844s1.723 4.844 4.27 4.844c2.148 0 3.846-1.453 4.22-3.646h1.899c-.475 3.239-2.922 5.431-6.119 5.431Zm14.693 0c-3.746 0-6.268-2.652-6.268-6.63s2.523-6.629 6.268-6.629c3.746 0 6.269 2.652 6.269 6.63 0 3.976-2.523 6.628-6.269 6.628Zm0-1.786c2.548 0 4.27-1.937 4.27-4.844s-1.722-4.844-4.27-4.844-4.27 1.938-4.27 4.844 1.723 4.844 4.27 4.844m18.066-11.218v12.748h-1.997V16.361h-4.895v10.963H74.59V16.361h-1.998v-1.785h1.998v-1.428c0-2.141 1.374-3.569 3.446-3.569.325 0 .724.102 1 .255v1.606h-.85c-.949 0-1.598.689-1.598 1.709v1.427zm-1.997-4.742h1.997v2.805h-1.997zm4.604 17.49 4.82-6.705-4.37-6.043h2.447l3.071 4.411 3.047-4.41h2.422l-4.32 6.042L98 27.324h-2.447l-3.497-5.074-3.52 5.074z"
      />
      <path
        fill="#42B3A2"
        fillRule="evenodd"
        clipRule="evenodd"
        d="m.774 9.695 8.903 5.659L26 .579 9.677 21.012zm24.452 17.768-8.903-5.658L0 36.579l16.323-20.433z"
      />
    </svg>
  );
}

// Just the zigzag mark (no wordmark) - for compact square badges.
export function EcofixMark({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 37" fill="none" className={className}>
      <path
        fill="#42B3A2"
        fillRule="evenodd"
        clipRule="evenodd"
        d="m.774 9.695 8.903 5.659L26 .579 9.677 21.012zm24.452 17.768-8.903-5.658L0 36.579l16.323-20.433z"
      />
    </svg>
  );
}
