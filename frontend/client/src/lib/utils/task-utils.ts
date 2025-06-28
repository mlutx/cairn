/**
 * Generates initials from a full name
 * @param name - The full name (e.g., "John Doe" or "Alice")
 * @returns The initials (e.g., "JD" or "A")
 */
export function getInitials(name: string): string {
  if (!name || typeof name !== 'string') {
    return '';
  }

  return name
    .split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .join('')
    .slice(0, 3); // Limit to 3 characters for better display
}
