export type ResumeEntry = {
  name?: string | null
  description?: string | null
  job_title?: string | null
  company?: string | null
  start_date?: string | null
  end_date?: string | null
  responsibilities?: string[]
  technologies?: string[]
}

export type ResumeExtractionResult = {
  document: {
    filename: string | null
    total_pages: number
  }
  personal_information: {
    full_name?: string | null
    headline?: string | null
    location?: string | null
    email?: string | null
    summary?: string | null
  }
  social_profiles: Record<string, string | string[] | null>
  skills: Record<string, string[]>
  projects: ResumeEntry[]
  experience: ResumeEntry[]
  education: ResumeEntry[]
  certifications: ResumeEntry[]
  achievements: ResumeEntry[]
}

type UploadResponse = {
  resume_id: string
  owner_token: string
}

type StatusResponse = {
  status: 'uploaded' | 'processing' | 'completed' | 'failed'
  progress: number
  detail: string | null
  error: { message: string } | null
}

const API_URL = process.env.NEXT_PUBLIC_RESUME_API_URL ?? 'http://localhost:8000'
const BASE_URL = `${API_URL}/api/v1/resumes`

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>

  const body = await response.json().catch(() => null)
  throw new Error(body?.detail?.message ?? `Resume service request failed (${response.status})`)
}

function uploadResume(file: File, onProgress: (progress: number) => void): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${BASE_URL}/upload`)
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 35))
    }
    request.onload = () => {
      try {
        const body = JSON.parse(request.responseText)
        if (request.status === 201) resolve(body)
        else reject(new Error(body?.detail?.message ?? 'Resume upload failed'))
      } catch {
        reject(new Error('Resume upload returned an invalid response'))
      }
    }
    request.onerror = () => reject(new Error('Cannot reach the resume extraction service'))
    const form = new FormData()
    form.append('file', file)
    request.send(form)
  })
}

async function startExtraction(upload: UploadResponse) {
  return parseResponse<StatusResponse>(await fetch(`${BASE_URL}/extract`, {
    method: 'POST',
    headers: { 'X-Owner-Token': upload.owner_token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: upload.resume_id }),
  }))
}

async function waitForExtraction(upload: UploadResponse, onProgress: (progress: number, detail: string) => void) {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    const status = await parseResponse<StatusResponse>(await fetch(`${BASE_URL}/${upload.resume_id}/status`, {
      headers: { 'X-Owner-Token': upload.owner_token },
    }))
    onProgress(35 + Math.round(status.progress * 65), status.detail ?? 'Extracting resume information')
    if (status.status === 'completed') return
    if (status.status === 'failed') throw new Error(status.error?.message ?? 'Resume extraction failed')
    await new Promise((resolve) => window.setTimeout(resolve, 500))
  }
  throw new Error('Resume extraction timed out. Please try again.')
}

export async function extractResume(
  file: File,
  onProgress: (progress: number, detail: string) => void,
): Promise<ResumeExtractionResult> {
  const upload = await uploadResume(file, (progress) => onProgress(progress, 'Uploading resume'))
  await startExtraction(upload)
  await waitForExtraction(upload, onProgress)
  return parseResponse<ResumeExtractionResult>(await fetch(`${BASE_URL}/${upload.resume_id}/result`, {
    headers: { 'X-Owner-Token': upload.owner_token },
  }))
}
