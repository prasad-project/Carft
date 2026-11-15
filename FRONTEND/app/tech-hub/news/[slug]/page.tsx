'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import type { Story } from '@/components/tech-hub/tech-hub-data'
import { fetchTechStory } from '@/components/tech-hub/tech-hub-api'
import '@/app/tech-hub/tech-hub.css'

export default function TechNewsArticlePage() {
  const { slug } = useParams<{ slug: string }>()
  const [story, setStory] = useState<Story | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    fetchTechStory(slug, controller.signal)
      .then(setStory)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Unable to load this story')
      })
    return () => controller.abort()
  }, [slug])

  return (
    <main className="hub-page" id="top">
      <header className="hub-nav">
        <div className="hub-nav-inner">
          <Link className="hub-logo" href="/tech-hub">Crafdeck</Link>
        </div>
      </header>
      <article className="hub-article-page hub-container">
        <Link className="hub-article-back" href="/tech-hub">← Back to Tech Hub</Link>
        {!story && !error && <div className="hub-empty-state"><strong>Loading story...</strong></div>}
        {error && <div className="hub-empty-state"><strong>Could not load this story.</strong><span>{error}</span></div>}
        {story && <><span className="hub-chip hub-chip-blue">{story.category}</span><h1>{story.title}</h1><div className="hub-byline"><span>{story.source}</span><span>· {story.dateLabel}</span></div><p className="hub-article-summary">{story.summary}</p>{story.originalUrl && <a className="hub-read-more" href={story.originalUrl} target="_blank" rel="noreferrer">Read original article <span aria-hidden="true">↗</span></a>}</>}
      </article>
    </main>
  )
}
