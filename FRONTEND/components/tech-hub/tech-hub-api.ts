import type { Story, VideoTopic } from './tech-hub-data'

type NewsArticle = {
  id: number
  title: string
  slug: string
  source_name: string
  original_url: string
  thumbnail_url: string | null
  description: string | null
  summary: string | null
  category: string | null
  tags: string[]
  published_at: string
  content_type: string
  views_count: number
  likes_count: number
  comments_count: number
}

type NewsResponse = {
  data: NewsArticle[]
  meta: { page: number; page_size: number; total: number }
}

const categoryLabels: Record<string, string> = {
  'artificial-intelligence': 'Artificial Intelligence',
  'machine-learning': 'Machine Learning',
  'generative-ai': 'Generative AI',
  'data-science': 'Data Science',
  programming: 'Programming',
  'developer-tools': 'Developer Tools',
  'open-source': 'Open Source',
  cybersecurity: 'Cybersecurity',
  'cloud-computing': 'Cloud Computing',
  'technology-business': 'Technology Business',
}

function apiUrl(path: string) {
  const baseUrl = process.env.NEXT_PUBLIC_TECHNEWS_API_URL ?? 'http://localhost:8000'
  return `${baseUrl.replace(/\/$/, '')}${path}`
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date)
}

function readCount(value: number) {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k reads`
  return `${value} reads`
}

function toStory(article: NewsArticle, index: number): Story {
  const category = article.category ? categoryLabels[article.category] ?? article.category : 'Technology'
  const summary = article.summary || article.description || 'Read the latest technology update from the original publisher.'
  return {
    id: String(article.id),
    slug: article.slug,
    originalUrl: article.original_url,
    title: article.title,
    category,
    summary,
    source: article.source_name,
    date: article.published_at,
    dateLabel: formatDate(article.published_at),
    readTime: Math.max(1, Math.ceil(summary.split(/\s+/).length / 12)),
    likes: article.likes_count,
    comments: article.comments_count,
    reads: readCount(article.views_count),
    art: ['orange-orb', 'purple-blocks', 'target', 'dot-orb', 'green-wave', 'navy-orb'][index % 6] as Story['art'],
    topics: article.tags,
  }
}

async function fetchNews(path: string, signal?: AbortSignal) {
  const response = await fetch(apiUrl(path), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`Tech News API returned ${response.status}`)
  const payload = await response.json() as NewsResponse
  return payload.data
}

export function fetchTechStories(sort: 'latest' | 'top', query: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ page: '1', page_size: '50', sort })
  if (query.trim()) params.set('q', query.trim())
  return fetchNews(`/api/news?${params.toString()}`, signal).then((articles) => articles.map(toStory))
}

export function fetchTechTopicStories(topic: VideoTopic, signal?: AbortSignal) {
  const paths: Record<VideoTopic, string> = {
    'Featured / Top stories': '/api/news/top?page=1&page_size=50',
    'Trending now': '/api/news/trending?page=1&page_size=50',
    'AI & machine learning': '/api/news/collections/ai-ml?page=1&page_size=50',
    'Developer discoveries': '/api/news/collections/developer-discoveries?page=1&page_size=50',
    'Latest research & open source': '/api/news/collections/research-open-source?page=1&page_size=50',
  }
  return fetchNews(paths[topic], signal).then((articles) => articles.map(toStory))
}

export async function fetchTechStory(slug: string, signal?: AbortSignal) {
  const response = await fetch(apiUrl(`/api/news/${encodeURIComponent(slug)}`), { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`Tech News API returned ${response.status}`)
  const payload = await response.json() as { data: NewsArticle }
  return toStory(payload.data, 0)
}
