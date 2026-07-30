import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

Element.prototype.scrollIntoView = function scrollIntoView() {
  /* jsdom stub */
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})
