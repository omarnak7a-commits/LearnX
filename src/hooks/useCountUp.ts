import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'

interface CountUpOptions {
  duration?: number
  delay?: number
  decimals?: number
  suffix?: string
}

export function useCountUp<T extends HTMLElement = HTMLSpanElement>(
  target: number,
  { duration = 2.2, delay = 0, decimals = 0 }: CountUpOptions = {}
) {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true) },
      { threshold: 0.4 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!inView) return
    const el = ref.current
    if (!el) return

    const controls = animate(0, target, {
      duration,
      delay,
      ease: [0.16, 1, 0.3, 1],
      onUpdate(v) {
        el.textContent = decimals > 0
          ? v.toFixed(decimals)
          : Math.round(v).toLocaleString()
      },
    })
    return () => controls.stop()
  }, [inView, target, duration, delay, decimals])

  return ref
}
