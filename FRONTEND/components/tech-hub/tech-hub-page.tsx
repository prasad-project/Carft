'use client'

import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import Link from 'next/link'
import BrandLogo from '../brand-logo'
import { Bookmark, Menu, Search, X } from 'lucide-react'
import {
  videoTopics,
} from './tech-hub-data'
import type { Story, VideoTopic } from './tech-hub-data'
import { fetchTechStories, fetchTechTopicStories } from './tech-hub-api'
import { PopularLists, StoryCard } from './tech-hub-sections'

type SortMode = 'Latest' | 'Top stories'

function HubNavigation() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const links = [
    { label: 'Home', href: '/' },
    { label: 'Developers', href: '/#developers' },
    { label: 'Arena', href: '/arena' },
    { label: 'Tech Hub', href: '/tech-hub' },
    { label: 'Pricing', href: '/#pricing' },
  ]

  return (
    <header className="hub-nav">
      <div className="hub-nav-inner">
        <BrandLogo className="hub-logo" />
        <nav className="hub-nav-links" aria-label="Main navigation">
          {links.map((link) => <Link key={link.label} href={link.href} aria-current={link.label === 'Tech Hub' ? 'page' : undefined} className={link.label === 'Tech Hub' ? 'is-current' : undefined}>{link.label}</Link>)}
        </nav>
        <span className="hub-profile-avatar" role="img" aria-label="Crafdeck member profile"><span className="hub-avatar-hair"/><span className="hub-avatar-face"/><span className="hub-avatar-body"/></span>
        <button className="hub-mobile-toggle" type="button" aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={mobileOpen} onClick={() => setMobileOpen((open) => !open)}>
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      {mobileOpen && <nav className="hub-mobile-nav" aria-label="Mobile navigation">{links.map((link) => <Link key={link.label} href={link.href} onClick={() => setMobileOpen(false)}>{link.label}</Link>)}</nav>}
    </header>
  )
}

function HubMasthead({
  searchQuery,
  onSearchChange,
  savedCount,
  savedOnly,
  onToggleSaved,
}: {
  searchQuery: string
  onSearchChange: (value: string) => void
  savedCount: number
  savedOnly: boolean
  onToggleSaved: () => void
}) {
  const onSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault()
  }

  const submitSearch = (event: FormEvent<HTMLFormElement>) => event.preventDefault()

  return (
    <section className="hub-masthead">
      <div className="hub-container">
        <div className="hub-search-row">
          <form className="hub-search-form" role="search" onSubmit={submitSearch}>
            <Search size={20} aria-hidden="true" />
            <label className="sr-only" htmlFor="hub-search">Search news, topics, tools, companies and tutorials</label>
            <input id="hub-search" type="search" value={searchQuery} onChange={(event) => onSearchChange(event.target.value)} onKeyDown={onSearchKeyDown} placeholder="Search news, topics, tools, companies and tutorials" />
            <button className="hub-search-submit" type="submit">Search</button>
          </form>
          <button type="button" className={`hub-saved-button ${savedOnly ? 'is-active' : ''}`} aria-pressed={savedOnly} onClick={onToggleSaved}><Bookmark size={16} /> Saved ({savedCount})</button>
        </div>
      </div>
    </section>
  )
}

function LatestNews({
  stories: visibleStories,
  allCount,
  sortMode,
  onSortChange,
  likedIds,
  savedIds,
  onLike,
  onSave,
  onShare,
  onLoadMore,
  hasMore,
  savedOnly,
  isLoading,
  error,
}: {
  stories: Story[]
  allCount: number
  sortMode: SortMode
  onSortChange: (sort: SortMode) => void
  likedIds: Set<string>
  savedIds: Set<string>
  onLike: (id: string) => void
  onSave: (id: string) => void
  onShare: (id: string) => void
  onLoadMore: () => void
  hasMore: boolean
  savedOnly: boolean
  isLoading: boolean
  error: string | null
}) {
  return (
    <section className="hub-section" aria-labelledby="hub-latest-title" id="latest-news">
      <div className="hub-container">
        <div className="hub-latest-heading">
          <h2 className="hub-section-title" id="hub-latest-title">Latest Technology News</h2>
          <div className="hub-sort-controls"><span>Sort by</span><div className="hub-sort-segment" role="group" aria-label="Sort stories">{(['Latest', 'Top stories'] as SortMode[]).map((sort) => <button key={sort} type="button" aria-pressed={sortMode === sort} className={sortMode === sort ? 'is-active' : ''} onClick={() => onSortChange(sort)}>{sort}</button>)}</div></div>
        </div>
        {isLoading ? <div className="hub-empty-state"><strong>Loading technology news...</strong></div> : error ? <div className="hub-empty-state"><strong>Could not load technology news.</strong><span>{error}</span></div> : visibleStories.length > 0 ? <div className="hub-story-grid">{visibleStories.map((story) => <StoryCard key={story.id} story={story} liked={likedIds.has(story.id)} saved={savedIds.has(story.id)} onLike={() => onLike(story.id)} onSave={() => onSave(story.id)} onShare={() => onShare(story.id)} />)}</div> : <div className="hub-empty-state"><strong>{savedOnly ? 'No saved stories match this view.' : 'No stories found.'}</strong><span>Try another topic or search term.</span></div>}
        {allCount > 0 && <div className="hub-load-more-wrap">{hasMore && <button type="button" className="hub-load-more" onClick={onLoadMore}>Load more stories</button>}<p>Showing {visibleStories.length} of {allCount} stories{hasMore ? ' · or load more' : ''}</p></div>}
      </div>
    </section>
  )
}

function TrendingTopics({ activeTopic, onTopicChange }: { activeTopic: VideoTopic | null; onTopicChange: (topic: VideoTopic) => void }) {
  return (
    <section className="hub-section hub-cream-section" aria-labelledby="hub-topics-title">
      <div className="hub-container">
        <h2 className="hub-section-title" id="hub-topics-title">Trending Topics</h2>
        <p className="hub-section-subtitle">Choose a topic to filter the videos below.</p>
        <div className="hub-topics">{videoTopics.map((topic) => {
          const active = activeTopic === topic
          return <button key={topic} type="button" className={`hub-topic ${active ? 'is-active' : ''}`} aria-pressed={activeTopic === topic} onClick={() => onTopicChange(topic)}>#{topic}</button>
        })}</div>
      </div>
    </section>
  )
}

function TopicNewsSection({ activeTopic, stories: topicStories, isLoading, error, onTopicChange, likedIds, savedIds, onLike, onSave, onShare }: { activeTopic: VideoTopic | null; stories: Story[]; isLoading: boolean; error: string | null; onTopicChange: (topic: VideoTopic) => void; likedIds: Set<string>; savedIds: Set<string>; onLike: (id: string) => void; onSave: (id: string) => void; onShare: (id: string) => void }) {
  return (
    <section className="hub-section hub-cream-section" aria-labelledby="hub-videos-title">
      <div className="hub-container">
        <h2 className="hub-section-title" id="hub-videos-title">{activeTopic ?? 'Explore technology topics'}</h2>
        <p className="hub-section-subtitle">{activeTopic ? `Related news for ${activeTopic}.` : 'Choose a topic to explore related technology news.'}</p>
        {isLoading ? <div className="hub-empty-state"><strong>Loading related news...</strong></div> : error ? <div className="hub-empty-state"><strong>Could not load related news.</strong><span>{error}</span></div> : activeTopic && topicStories.length > 0 ? <div className="hub-topic-news-strip">{topicStories.map((story) => <StoryCard key={story.id} story={story} showArtwork={false} liked={likedIds.has(story.id)} saved={savedIds.has(story.id)} onLike={() => onLike(story.id)} onSave={() => onSave(story.id)} onShare={() => onShare(story.id)} />)}</div> : activeTopic ? <div className="hub-empty-state"><strong>No related news found.</strong><span>Try another topic to explore more stories.</span></div> : <div className="hub-video-topic-grid">{videoTopics.map((topic) => <button key={topic} type="button" className="hub-video-topic-card" onClick={() => onTopicChange(topic)}><strong>#{topic}</strong><span>Explore related technology news</span></button>)}</div>}
      </div>
    </section>
  )
}

function HubFooter() {
  return <footer className="hub-footer"><div className="hub-container"><span>Content is curated and published by the Crafdeck editorial team. Original publishers keep all rights to their articles and videos.</span><span>© 2026 Crafdeck</span></div></footer>
}

export default function TechHubPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [sortMode, setSortMode] = useState<SortMode>('Latest')
  const [activeTopic, setActiveTopic] = useState<VideoTopic | null>(null)
  const [newsStories, setNewsStories] = useState<Story[]>([])
  const [topicStories, setTopicStories] = useState<Story[]>([])
  const [newsLoading, setNewsLoading] = useState(true)
  const [topicLoading, setTopicLoading] = useState(false)
  const [newsError, setNewsError] = useState<string | null>(null)
  const [topicError, setTopicError] = useState<string | null>(null)
  const [savedOnly, setSavedOnly] = useState(false)
  const [savedIds, setSavedIds] = useState(() => new Set<string>())
  const [likedIds, setLikedIds] = useState(() => new Set<string>())
  const [savedCount, setSavedCount] = useState(0)
  const [visibleCount, setVisibleCount] = useState(6)
  const [shareMessage, setShareMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setNewsLoading(true)
    setNewsError(null)
    fetchTechStories(sortMode === 'Latest' ? 'latest' : 'top', searchQuery, controller.signal)
      .then(setNewsStories)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setNewsError(error instanceof Error ? error.message : 'Unexpected API error')
      })
      .finally(() => {
        if (!controller.signal.aborted) setNewsLoading(false)
      })
    return () => controller.abort()
  }, [searchQuery, sortMode])

  useEffect(() => {
    if (!activeTopic) {
      setTopicStories([])
      setTopicLoading(false)
      setTopicError(null)
      return
    }
    const controller = new AbortController()
    setTopicLoading(true)
    setTopicError(null)
    fetchTechTopicStories(activeTopic, controller.signal)
      .then(setTopicStories)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setTopicError(error instanceof Error ? error.message : 'Unexpected API error')
      })
      .finally(() => {
        if (!controller.signal.aborted) setTopicLoading(false)
      })
    return () => controller.abort()
  }, [activeTopic])

  const filteredStories = useMemo(() => {
    const filtered = newsStories.filter((story) => !savedOnly || savedIds.has(story.id))

    return filtered
  }, [newsStories, savedIds, savedOnly])

  const visibleStories = filteredStories.slice(0, visibleCount)
  const storyLookup = new Map(newsStories.map((story) => [story.id, story]))
  const popularLists = useMemo(() => [
    { title: 'Top stories', metric: 'reads', storyIds: [...newsStories].sort((a, b) => Number.parseFloat(b.reads) - Number.parseFloat(a.reads)).slice(0, 5).map((story) => story.id) },
    { title: 'Most liked', metric: 'likes', storyIds: [...newsStories].sort((a, b) => b.likes - a.likes).slice(0, 5).map((story) => story.id) },
    { title: 'Most discussed', metric: 'comments', storyIds: [...newsStories].sort((a, b) => b.comments - a.comments).slice(0, 5).map((story) => story.id) },
  ], [newsStories])

  const toggleLike = (id: string) => setLikedIds((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const toggleSave = (id: string) => {
    const removing = savedIds.has(id)
    setSavedIds((current) => {
      const next = new Set(current)
      if (removing) next.delete(id)
      else next.add(id)
      return next
    })
    setSavedCount((count) => Math.max(0, count + (removing ? -1 : 1)))
  }

  const shareStory = (id: string) => {
    const story = storyLookup.get(id)
    if (!story || typeof window === 'undefined') return
    const url = `${window.location.origin}/tech-hub#story-${id}`
    const shareData = { title: story.title, url }
    if (navigator.share) {
      void navigator.share(shareData).catch(() => undefined)
      return
    }
    if (navigator.clipboard) void navigator.clipboard.writeText(url).then(() => setShareMessage(`Link copied for ${story.title}`)).catch(() => setShareMessage('Could not copy the story link.'))
  }

  const changeTopic = (topic: VideoTopic) => {
    setActiveTopic((current) => current === topic ? null : topic)
    setVisibleCount(6)
    document.getElementById('hub-videos-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <main className="hub-page" id="top">
      <HubNavigation />
      <HubMasthead searchQuery={searchQuery} onSearchChange={(value) => { setSearchQuery(value); setVisibleCount(6) }} savedCount={savedCount} savedOnly={savedOnly} onToggleSaved={() => { setSavedOnly((current) => !current); setActiveTopic(null); setVisibleCount(6) }} />
      <LatestNews stories={visibleStories} allCount={filteredStories.length} sortMode={sortMode} onSortChange={(nextSort) => { setSortMode(nextSort); setVisibleCount(6) }} likedIds={likedIds} savedIds={savedIds} onLike={toggleLike} onSave={toggleSave} onShare={shareStory} onLoadMore={() => setVisibleCount((count) => count + 6)} hasMore={visibleCount < filteredStories.length} savedOnly={savedOnly} isLoading={newsLoading} error={newsError} />
      <TrendingTopics activeTopic={activeTopic} onTopicChange={changeTopic} />
      <TopicNewsSection activeTopic={activeTopic} stories={topicStories} isLoading={topicLoading} error={topicError} onTopicChange={changeTopic} likedIds={likedIds} savedIds={savedIds} onLike={toggleLike} onSave={toggleSave} onShare={shareStory} />
      <PopularLists lists={popularLists} stories={newsStories} />
      <HubFooter />
      <div className="hub-share-status" role="status" aria-live="polite">{shareMessage}</div>
    </main>
  )
}
