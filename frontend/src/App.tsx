import { type ReactElement, useCallback, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import {
  Factory,
  Leaf,
  Lock,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatINR, formatINRPerTonne, formatIndianNumber } from './currency.js'

type User = {
  id: number
  username: string
  email: string
  role: string
  organization: string | null
}

type Material = {
  id: number
  title: string
  material_type: string
  category: string
  location: string
  quantity: number
  unit: string
  public_summary: string
  sensitive_notes?: string
  properties?: Array<Record<string, unknown>>
  is_public: boolean
  price_per_ton?: number | null
  price_original_amount: number | null
  price_original_currency_code: string | null
  price_original_unit: string | null
  currency_code: string
  price_unit: string
  price_available: boolean
  gst_rate_percent: number | null
  gst_inclusive: boolean | null
  price_source_org: string | null
  price_source_title: string | null
  price_source_url: string | null
  price_publication_date: string | null
  price_retrieved_date: string | null
  price_geographic_coverage: string | null
  price_grade: string | null
  price_limitations: string | null
  price_last_updated: string | null
  price_verification_status: string
  price_valid_until: string | null
  price_status: string
  city: string | null
  state: string | null
  owner_id: number
  organization: string | null
  verification_status: string
  demo_label: string
  status: string
}

type Requirement = {
  id: number
  title: string
  material_category: string
  technical_specs: string
  quantity: number
  unit: string
  location: string
  city: string | null
  state: string | null
  safety_constraints: string
  max_distance_km: number
}

type SourcedReference = {
  id: number
  slug: string
  reference_type: string
  name: string
  value: number | null
  qualifier: string | null
  unit: string
  currency_code: string | null
  reporting_period: string | null
  source_org: string
  source_title: string
  source_url: string
  publication_date: string | null
  retrieved_date: string
  geographic_coverage: string
  material_grade: string | null
  data_classification: string
  verification_status: string
  methodology: string
  limitations: string
  last_updated: string
}

const API_BASE = '/api'
const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana',
  'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
  'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
]
const CATEGORIES = ['biomass', 'construction', 'metals', 'packaging', 'plastics', 'textiles']

async function apiRequest<T>(path: string, method = 'GET', token?: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail ?? 'Request failed')
  }
  return data as T
}

function QuotationRequestAction({ item, token, canRequest }: { item: Material; token: string | null; canRequest: boolean }) {
  const [open, setOpen] = useState(false)
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('tonnes')
  const [deliveryLocation, setDeliveryLocation] = useState('')
  const [message, setMessage] = useState('')
  const [savedId, setSavedId] = useState<number | null>(null)
  const [error, setError] = useState('')

  if (item.price_available || !canRequest) return null

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    try {
      const response = await apiRequest<{ item: { id: number; status: string } }>('/quotation-requests', 'POST', token ?? undefined, {
        listing_id: item.id,
        requested_quantity: Number(quantity),
        quantity_unit: unit,
        delivery_location: deliveryLocation,
        message,
      })
      if (!response.item?.id || response.item.status !== 'pending') {
        throw new Error('The server did not confirm that the quotation request was saved.')
      }
      setSavedId(response.item.id)
      setOpen(false)
      setQuantity('')
      setDeliveryLocation('')
      setMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save quotation request.')
    }
  }

  return (
    <div className="mt-4">
      {savedId !== null && <div role="status" className="mb-3 rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-700">Quotation request #{savedId} saved for {item.title}.</div>}
      {open ? (
        <form className="space-y-3 rounded-xl border border-slate-200 p-3" onSubmit={submit}>
          <h3 className="font-semibold">Request supplier quotation</h3>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <div><label className="label">Requested quantity</label><input required min="0.001" step="any" type="number" className="field" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
            <div><label className="label">Unit</label><select className="field" value={unit} onChange={(event) => setUnit(event.target.value)}><option value="tonnes">tonnes</option><option value="kg">kg</option></select></div>
          </div>
          <div><label className="label">Delivery location</label><input required maxLength={240} className="field" value={deliveryLocation} onChange={(event) => setDeliveryLocation(event.target.value)} placeholder="City, state" /></div>
          <div><label className="label">Message (optional)</label><textarea maxLength={2000} className="field min-h-20" value={message} onChange={(event) => setMessage(event.target.value)} /></div>
          {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <div className="flex gap-2"><button type="submit" className="primary-btn">Send quotation request</button><button type="button" className="secondary-btn" onClick={() => { setOpen(false); setError('') }}>Cancel</button></div>
        </form>
      ) : (
        <button className="primary-btn w-full" onClick={() => setOpen(true)}>Request quotation</button>
      )}
    </div>
  )
}

function DataSourcesSection({ className = '' }: { className?: string }) {
  const [items, setItems] = useState<SourcedReference[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<{ items: SourcedReference[] }>('/data-sources')
      .then((data) => setItems(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load data sources'))
  }, [])

  const displayValue = (item: SourcedReference) => {
    if (item.value === null) {
      return item.reference_type === 'index_context'
        ? 'Index value unavailable — not a selling price'
        : 'No observation imported'
    }
    if (item.currency_code === 'INR') {
      return item.unit === 'INR/tonne' ? formatINRPerTonne(item.value) : formatINR(item.value)
    }
    return `${item.qualifier ? `${item.qualifier} ` : ''}${formatIndianNumber(item.value)} ${item.unit}`
  }

  return (
    <section className={`card p-6 ${className}`}>
      <h2 className="text-xl font-semibold text-slate-900">Data Sources &amp; Methodology</h2>
      <p className="mt-2 text-sm text-slate-600">Official national references are separate from company listings. Source-claimed or missing values are not independently verified and are not used as verified impact factors or material prices.</p>
      {error && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {items.map((item) => (
          <article key={item.slug} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h3 className="font-semibold text-slate-900">{item.name}</h3>
              <div className="flex gap-2">
                <span className="badge">{item.data_classification.replace(/_/g, ' ')}</span>
                <span className="badge">{item.verification_status.replace(/-/g, ' ')}</span>
              </div>
            </div>
            <div className="mt-2 text-lg font-bold text-emerald-800">{displayValue(item)}</div>
            {item.reporting_period && <div className="mt-1 text-sm text-slate-600">Reporting period: {item.reporting_period}</div>}
            {item.material_grade && <div className="mt-1 text-sm text-slate-600">Grade: {item.material_grade}</div>}
            <div className="mt-2 text-sm text-slate-600">{item.source_org} · {item.source_title}</div>
            <div className="mt-1 text-xs text-slate-500">
              Coverage: {item.geographic_coverage}
              {item.publication_date ? ` · Published ${item.publication_date}` : ''}
              {` · Retrieved ${item.retrieved_date}`}
            </div>
            <div className="mt-2 text-xs text-slate-600">{item.methodology}</div>
            <div className="mt-1 text-xs text-amber-800">{item.limitations}</div>
            <a className="mt-2 inline-block text-sm text-emerald-700 underline" href={item.source_url} target="_blank" rel="noreferrer">Open source</a>
          </article>
        ))}
      </div>
    </section>
  )
}

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('cm_token'))
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem('cm_user')
      return raw ? (JSON.parse(raw) as User) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    if (!token) {
      localStorage.removeItem('cm_token')
      localStorage.removeItem('cm_user')
      return
    }
    localStorage.setItem('cm_token', token)
    apiRequest<{ user: User }>('/auth/me', 'GET', token)
      .then((result) => {
        setUser(result.user)
        localStorage.setItem('cm_user', JSON.stringify(result.user))
      })
      .catch(() => {
        setUser(null)
        setToken(null)
      })
  }, [token])

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('cm_token')
    localStorage.removeItem('cm_user')
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-800">
        <Header user={user} logout={logout} />
        <Routes>
          <Route path="/" element={<LandingPage user={user} />} />
          <Route path="/login" element={<LoginPage setToken={setToken} setUser={setUser} token={token} />} />
          <Route path="/dashboard" element={<ProtectedRoute token={token}><DashboardPage token={token} /></ProtectedRoute>} />
          <Route path="/materials" element={<ProtectedRoute token={token}><ListingsPage token={token} /></ProtectedRoute>} />
          <Route path="/marketplace" element={<ProtectedRoute token={token}><MarketplacePage token={token} /></ProtectedRoute>} />
          <Route path="/requirements" element={<ProtectedRoute token={token}><RequirementsPage token={token} /></ProtectedRoute>} />
          <Route path="/matches" element={<ProtectedRoute token={token}><MatchResultsPage token={token} /></ProtectedRoute>} />
          <Route path="/matches/:id" element={<ProtectedRoute token={token}><MatchDetailPage token={token} /></ProtectedRoute>} />
          <Route path="/verification" element={<ProtectedRoute token={token}><VerificationPage token={token} /></ProtectedRoute>} />
          <Route path="/privacy" element={<ProtectedRoute token={token}><PrivacyPage token={token} /></ProtectedRoute>} />
          <Route path="/impact" element={<ProtectedRoute token={token}><ImpactCalculatorPage token={token} /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute token={token}><AnalyticsPage token={token} /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute token={token}><AdminReviewPage token={token} /></ProtectedRoute>} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

function ProtectedRoute({ token, children }: { token: string | null; children: ReactElement }) {
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return children
}

function Header({ user, logout }: { user: User | null; logout: () => void }) {
  const navItems = [
    { label: 'Home', href: '/' },
    { label: 'Dashboard', href: '/dashboard' },
    { label: 'Marketplace', href: '/marketplace' },
    { label: 'Requirements', href: '/requirements' },
    { label: 'Matches', href: '/matches' },
    { label: 'Impact', href: '/impact' },
    { label: 'Analytics', href: '/analytics' },
  ]

  return (
    <header className="border-b border-emerald-100 bg-white/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 lg:px-8">
        <Link to="/" className="flex items-center gap-3 text-lg font-bold text-emerald-900">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-700 text-white">
            <Leaf className="h-5 w-5" />
          </div>
          CircularMatch AI
        </Link>
        <nav className="hidden items-center gap-6 md:flex">
          {navItems.map((item) => (
            <Link key={item.href} to={item.href} className="text-sm font-medium text-slate-700 hover:text-emerald-700">
              {item.label}
            </Link>
          ))}
          {user?.role === 'admin' && (
            <Link to="/admin" className="text-sm font-medium text-slate-700 hover:text-emerald-700">Admin</Link>
          )}
        </nav>
        {user ? (
          <div className="flex items-center gap-3">
            <div className="hidden rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700 sm:block">
              {user.role}
            </div>
            <button className="secondary-btn" onClick={logout}>
              Logout
            </button>
          </div>
        ) : (
          <Link to="/login" className="primary-btn">
            Login
          </Link>
        )}
      </div>
    </header>
  )
}

function LandingPage({ user }: { user: User | null }) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-12 lg:px-8">
      <section className="rounded-[32px] bg-gradient-to-r from-emerald-900 via-emerald-800 to-teal-700 p-10 text-white shadow-xl">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <span className="badge border-emerald-400 bg-white/10 text-white">Industrial by-product intelligence</span>
            <h1 className="mt-5 text-4xl font-bold tracking-tight lg:text-6xl">Match waste streams to valuable reuse opportunities.</h1>
            <p className="mt-5 max-w-xl text-base text-emerald-50">
              CircularMatch AI helps producers, seekers, verifiers, and administrators confidently identify sustainable industrial exchanges with trust-aware intelligence and transparent impact calculations.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              {user ? (
                <Link to="/dashboard" className="primary-btn bg-white text-emerald-900 hover:bg-emerald-50">Open dashboard</Link>
              ) : (
                <Link to="/login" className="primary-btn bg-white text-emerald-900 hover:bg-emerald-50">Try the demo</Link>
              )}
              <Link to="/marketplace" className="secondary-btn border-white/30 bg-transparent text-white hover:bg-white/10">Explore marketplace</Link>
            </div>
          </div>
          <div className="rounded-[28px] bg-white/10 p-5 shadow-lg backdrop-blur-sm">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/20 bg-white/5 p-5">
                <div className="text-lg font-bold">INR-first</div>
                <div className="mt-2 text-sm text-emerald-100">Prices are shown in rupees per tonne when a quote is available.</div>
              </div>
              <div className="rounded-2xl border border-white/20 bg-white/5 p-5">
                <div className="text-lg font-bold">India-focused</div>
                <div className="mt-2 text-sm text-emerald-100">Search by Indian state, city, material and verification status.</div>
              </div>
            </div>
            <div className="mt-5 rounded-2xl border border-white/20 bg-white/5 p-4 text-sm text-emerald-50">
              Private data remains restricted. Source and verification metadata are shown where recorded; missing prices are not estimated.
            </div>
          </div>
        </div>
      </section>

      <section className="mt-12 grid gap-6 md:grid-cols-3">
        {[
          { icon: Factory, title: 'Producer workflows', text: 'Publish listings, manage access requests, and maintain evidence-backed metadata.' },
          { icon: ShieldCheck, title: 'Verification centre', text: 'Review missing, expired, and conflicting data before final trust decisions.' },
          { icon: TrendingUp, title: 'Impact engine', text: 'Model emissions, cost savings, and net benefit using documented assumptions.' },
        ].map(({ icon: Icon, title, text }) => (
          <div key={title} className="card p-6">
            <div className="mb-4 inline-flex rounded-xl bg-emerald-100 p-3 text-emerald-700">
              <Icon className="h-5 w-5" />
            </div>
            <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
            <p className="mt-3 text-slate-600">{text}</p>
          </div>
        ))}
      </section>
    </main>
  )
}

function LoginPage({ setToken, setUser, token }: { setToken: (value: string | null) => void; setUser: (value: User | null) => void; token: string | null }) {
  const navigate = useNavigate()
  const [username, setUsername] = useState('producer1')
  const [password, setPassword] = useState('demo123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (token) navigate('/dashboard')
  }, [navigate, token])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail ?? 'Login failed')
      }
      setToken(data.token)
      setUser(data.user)
      localStorage.setItem('cm_token', data.token)
      localStorage.setItem('cm_user', JSON.stringify(data.user))
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-12 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="card p-8">
          <h1 className="text-3xl font-bold text-slate-900">Welcome back</h1>
          <p className="mt-2 text-slate-600">Log in to manage material listings, access requests, and verification decisions.</p>
          <div className="mt-6 space-y-3 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <div className="text-sm font-semibold text-emerald-800">Demo credentials</div>
            <div className="text-sm text-emerald-700">Producer: producer1 / demo123</div>
            <div className="text-sm text-emerald-700">Seeker: seeker1 / demo123</div>
            <div className="text-sm text-emerald-700">Verifier: verifier1 / demo123</div>
            <div className="text-sm text-emerald-700">Admin: admin / demo123</div>
          </div>
        </div>
        <div className="card p-8">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="label">Username</label>
              <input className="field" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" className="field" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
            <button className="primary-btn w-full" type="submit" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </main>
  )
}

function DashboardPage({ token }: { token: string | null }) {
  const [stats, setStats] = useState<{ stats: Record<string, number> } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiRequest<{ stats: Record<string, number> }>('/dashboard', 'GET', token ?? undefined)
      .then((data) => setStats(data))
      .finally(() => setLoading(false))
  }, [token])

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-700">Dashboard</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Operational overview</h1>
        </div>
      </div>
      {loading ? <div className="card p-6">Loading...</div> : (
        <div className="grid gap-6 md:grid-cols-4">
          {stats && [
            { label: 'Materials', value: stats.stats.materials },
            { label: 'Public listings', value: stats.stats.public_materials },
            { label: 'Requirements', value: stats.stats.requirements },
            { label: 'Pending requests', value: stats.stats.pending_requests },
            { label: 'Verified listings', value: stats.stats.verified_listings },
          ].map((item) => (
            <div key={item.label} className="card p-6">
              <div className="text-sm text-slate-500">{item.label}</div>
              <div className="mt-3 text-3xl font-bold text-slate-900">{item.value}</div>
            </div>
          ))}
          {stats && (
            <div className="card p-6 md:col-span-2">
              <div className="text-sm text-slate-500">Recorded economic benefit (INR)</div>
              <div className="mt-3 text-3xl font-bold text-slate-900">{formatINR(stats.stats.estimated_economic_benefit_inr)}</div>
              <div className="mt-2 text-xs text-slate-500">Calculated from saved records with complete user-provided INR inputs only.</div>
            </div>
          )}
        </div>
      )}
      <DataSourcesSection className="mt-6" />
    </main>
  )
}

function ListingsPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Material[]>([])
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [quotationRequests, setQuotationRequests] = useState<Array<Record<string, any>>>([])
  const [title, setTitle] = useState('Fly Ash Cement Blend')
  const [materialType, setMaterialType] = useState('Fly ash')
  const [category, setCategory] = useState('construction')
  const [city, setCity] = useState('Hyderabad')
  const [state, setState] = useState('Telangana')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('tonnes')
  const [price, setPrice] = useState('')
  const [priceValidUntil, setPriceValidUntil] = useState('')
  const [originalPrice, setOriginalPrice] = useState('')
  const [originalPriceUnit, setOriginalPriceUnit] = useState('INR/tonne')
  const [gstRate, setGstRate] = useState('')
  const [gstInclusive, setGstInclusive] = useState('')
  const [priceSourceOrg, setPriceSourceOrg] = useState('')
  const [priceSourceTitle, setPriceSourceTitle] = useState('')
  const [priceSourceUrl, setPriceSourceUrl] = useState('')
  const [pricePublicationDate, setPricePublicationDate] = useState('')
  const [priceRetrievedDate, setPriceRetrievedDate] = useState('')
  const [priceCoverage, setPriceCoverage] = useState('')
  const [priceGrade, setPriceGrade] = useState('')
  const [priceLimitations, setPriceLimitations] = useState('')
  const [publicSummary, setPublicSummary] = useState('')
  const [status, setStatus] = useState('available')
  const [message, setMessage] = useState('')
  const [editingPriceId, setEditingPriceId] = useState<number | null>(null)
  const [editPrice, setEditPrice] = useState('')
  const [editPriceValidUntil, setEditPriceValidUntil] = useState('')
  const [editPriceSource, setEditPriceSource] = useState('')
  const [editPriceGrade, setEditPriceGrade] = useState('')
  const [editPriceUrl, setEditPriceUrl] = useState('')
  const [editPriceGst, setEditPriceGst] = useState('')
  const [editPriceGstInclusive, setEditPriceGstInclusive] = useState('')

  const load = useCallback(() => {
    apiRequest<{ items: Material[] }>('/materials', 'GET', token ?? undefined)
      .then((data) => setItems(data.items))
      .catch((e) => setMessage(e.message))
  }, [token])

  useEffect(() => {
    if (token) {
      apiRequest<{ user: User }>('/auth/me', 'GET', token)
        .then((data) => setCurrentUser(data.user))
        .catch((e) => setMessage(e.message))
    }
  }, [token])

  useEffect(() => {
    if (currentUser) {
      apiRequest<{ items: Array<Record<string, any>> }>('/quotation-requests', 'GET', token ?? undefined)
        .then((data) => setQuotationRequests(data.items))
        .catch((e) => setMessage(e.message))
    }
  }, [currentUser, token])

  useEffect(() => { load() }, [load])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await apiRequest('/materials', 'POST', token ?? undefined, {
        title,
        material_type: materialType,
        category,
        city,
        state,
        quantity: Number(quantity),
        unit,
        price_per_tonne: originalPrice
          ? Number(originalPrice) * (originalPriceUnit === 'INR/kg' ? 1000 : 1)
          : price ? Number(price) : null,
        currency_code: 'INR',
        price_original_amount: originalPrice ? Number(originalPrice) : null,
        price_original_currency_code: 'INR',
        price_original_unit: originalPrice ? originalPriceUnit : 'INR/tonne',
        gst_rate_percent: gstRate ? Number(gstRate) : null,
        gst_inclusive: gstInclusive === '' ? null : gstInclusive === 'true',
        price_source_org: priceSourceOrg || null,
        price_source_title: priceSourceTitle || null,
        price_source_url: priceSourceUrl || null,
        price_type: price ? 'market_quote' : null,
        price_valid_until: price ? priceValidUntil : null,
        price_publication_date: pricePublicationDate || null,
        price_retrieved_date: priceRetrievedDate || null,
        price_geographic_coverage: priceCoverage || null,
        price_grade: priceGrade || null,
        price_limitations: priceLimitations || null,
        public_summary: publicSummary,
        status,
      })
      setMessage('Material listing created successfully.')
      load()
    } catch (e) {
      setMessage((e as Error).message)
    }
  }

  const startPriceEdit = (item: Material) => {
    setEditingPriceId(item.id)
    setEditPrice(item.price_per_ton?.toString() ?? '')
    setEditPriceValidUntil(item.price_valid_until ?? '')
    setEditPriceSource(item.organization ?? '')
    setEditPriceGrade(item.price_grade ?? '')
    setEditPriceUrl(item.price_source_url ?? '')
    setEditPriceGst(item.gst_rate_percent?.toString() ?? '')
    setEditPriceGstInclusive(item.gst_inclusive === null ? '' : String(item.gst_inclusive))
    setMessage('')
  }

  const savePrice = async (event: React.FormEvent<HTMLFormElement>, item: Material) => {
    event.preventDefault()
    setMessage('')
    try {
      const response = await apiRequest<{ item: Material }>(`/materials/${item.id}/price`, 'PUT', token ?? undefined, {
        price_per_tonne: Number(editPrice),
        currency_code: 'INR',
        price_source_org: editPriceSource,
        price_source_title: 'Supplier quotation',
        price_source_url: editPriceUrl || null,
        price_valid_until: editPriceValidUntil,
        price_geographic_coverage: item.city && item.state ? `${item.city}, ${item.state}` : item.location,
        price_grade: editPriceGrade,
        gst_rate_percent: editPriceGst ? Number(editPriceGst) : null,
        gst_inclusive: editPriceGstInclusive === '' ? null : editPriceGstInclusive === 'true',
      })
      if (!response.item.price_available) {
        throw new Error('Price was saved but is not currently eligible for display; verify the quotation details and validity.')
      }
      setMessage(`Supplier quotation saved for ${item.title}.`)
      setEditingPriceId(null)
      load()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Unable to save supplier quotation.')
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
        {quotationRequests.length > 0 && <section className="card p-6 lg:col-span-2">
          <h2 className="text-xl font-semibold">Supplier quotation requests</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {quotationRequests.map((request) => (
              <div key={request.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3"><span className="font-semibold">{request.listing_title}</span><span className="badge">{request.status}</span></div>
                <div className="mt-2 text-sm text-slate-600">{formatIndianNumber(request.requested_quantity)} {request.quantity_unit} · Deliver to {request.delivery_location}</div>
                {request.message && <div className="mt-1 text-sm text-slate-600">{request.message}</div>}
              </div>
            ))}
          </div>
        </section>}
        <div className="card p-6">
          <h1 className="text-2xl font-bold text-slate-900">Material listings</h1>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {items.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-lg font-semibold">{item.title}</h2>
                  <span className="badge">{item.status}</span>
                </div>
                <p className="mt-2 text-sm text-slate-600">{item.public_summary}</p>
                <div className="mt-4 text-sm text-slate-700">
                  <div>{item.material_type} · {item.category}</div>
                  <div>{formatIndianNumber(item.quantity)} {item.unit}</div>
                  <div>{item.city && item.state ? `${item.city}, ${item.state}` : item.location}</div>
                  <div className="mt-2 font-semibold">{item.price_available && item.currency_code === 'INR' && item.price_per_ton != null ? formatINRPerTonne(item.price_per_ton) : 'Price unavailable — request a supplier quotation'}</div>
                  {item.price_available && item.price_original_amount !== null && item.price_original_currency_code === 'INR' && <div className="text-xs text-slate-500">Source amount: {item.price_original_unit === 'INR/tonne' ? formatINRPerTonne(item.price_original_amount) : `${formatINR(item.price_original_amount)} / ${item.price_original_unit}`}</div>}
                  {item.price_available && item.price_original_amount !== null && item.price_original_currency_code !== 'INR' && <div className="text-xs text-slate-500">Original source amount not displayed as INR (currency: {item.price_original_currency_code ?? 'unknown'}).</div>}
                  {item.price_available && <div className="text-xs text-slate-500">GST {item.gst_inclusive === null ? 'treatment not specified' : item.gst_inclusive ? 'inclusive' : 'exclusive'}{item.gst_rate_percent !== null ? ` · ${item.gst_rate_percent}%` : ''}</div>}
                  {item.price_source_title && <div className="text-xs text-slate-500">{item.price_source_org}: {item.price_source_title}</div>}
                  {item.price_source_url && <a className="text-xs text-emerald-700 underline" href={item.price_source_url} target="_blank" rel="noreferrer">Price source</a>}
                  {item.price_publication_date && <div className="text-xs text-slate-500">Published {item.price_publication_date}</div>}
                  {item.price_retrieved_date && <div className="text-xs text-slate-500">Received/retrieved {item.price_retrieved_date}</div>}
                  {item.price_geographic_coverage && <div className="text-xs text-slate-500">Coverage: {item.price_geographic_coverage}{item.price_grade ? ` · Grade: ${item.price_grade}` : ''}</div>}
                  {item.price_limitations && <div className="text-xs text-slate-500">Limitations: {item.price_limitations}</div>}
                  {item.price_last_updated && <div className="text-xs text-slate-500">Price updated {item.price_last_updated}</div>}
                  {item.price_available && <div className="text-xs text-slate-500">Supplier-price verification: {item.price_verification_status === 'verified' ? 'verified supplier price' : 'unverified supplier quotation'}</div>}
                  {item.price_valid_until && <div className="text-xs text-slate-500">Valid until {item.price_valid_until} · {item.price_status}</div>}
                  <div className="mt-2 text-xs font-semibold text-amber-700">{item.demo_label}</div>
                  {currentUser && (currentUser.role === 'admin' || currentUser.id === item.owner_id) && item.demo_label !== 'DEMONSTRATION DATA' && (
                    <div className="mt-3">
                      {editingPriceId === item.id ? (
                        <form className="space-y-2 rounded-xl border border-slate-200 p-3" onSubmit={(event) => savePrice(event, item)}>
                          <label className="label">Supplier price (INR/tonne)</label>
                          <input required min="0" step="any" type="number" className="field" value={editPrice} onChange={(event) => setEditPrice(event.target.value)} />
                          <label className="label">Valid until</label>
                          <input required type="date" className="field" value={editPriceValidUntil} onChange={(event) => setEditPriceValidUntil(event.target.value)} />
                          <label className="label">Supplier/source name</label>
                          <input required className="field" value={editPriceSource} onChange={(event) => setEditPriceSource(event.target.value)} />
                          <label className="label">Material grade / quality</label>
                          <input required className="field" value={editPriceGrade} onChange={(event) => setEditPriceGrade(event.target.value)} />
                          <label className="label">Quotation URL (optional)</label>
                          <input type="url" className="field" value={editPriceUrl} onChange={(event) => setEditPriceUrl(event.target.value)} />
                          <div className="grid grid-cols-2 gap-2">
                            <div><label className="label">GST rate % (optional)</label><input min="0" max="100" step="any" type="number" className="field" value={editPriceGst} onChange={(event) => setEditPriceGst(event.target.value)} /></div>
                            <div><label className="label">GST treatment</label><select className="field" value={editPriceGstInclusive} onChange={(event) => setEditPriceGstInclusive(event.target.value)}><option value="">Not specified</option><option value="true">Inclusive</option><option value="false">Exclusive</option></select></div>
                          </div>
                          <div className="flex gap-2"><button type="submit" className="primary-btn">Save price</button><button type="button" className="secondary-btn" onClick={() => setEditingPriceId(null)}>Cancel</button></div>
                        </form>
                      ) : (
                        <button className="secondary-btn mt-2 w-full" onClick={() => startPriceEdit(item)}>{item.price_available ? 'Update supplier price' : 'Add supplier price'}</button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-6">
          <h2 className="text-xl font-semibold">Create new listing</h2>
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div><label className="label">Title</label><input className="field" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><label className="label">Material type</label><input className="field" value={materialType} onChange={(e) => setMaterialType(e.target.value)} /></div>
            <div><label className="label">Category</label><select className="field" value={category} onChange={(e) => setCategory(e.target.value)}>{CATEGORIES.map((value) => <option key={value}>{value}</option>)}</select></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Quantity</label><input required min="0.001" type="number" step="any" className="field" value={quantity} onChange={(e) => setQuantity(e.target.value)} /></div>
              <div><label className="label">Unit</label><select className="field" value={unit} onChange={(e) => setUnit(e.target.value)}><option value="tonnes">tonnes</option><option value="kg">kg</option></select></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">State</label><select className="field" value={state} onChange={(e) => setState(e.target.value)}>{INDIAN_STATES.map((value) => <option key={value}>{value}</option>)}</select></div>
              <div><label className="label">City</label><input required className="field" value={city} onChange={(e) => setCity(e.target.value)} /></div>
            </div>
            <div><label className="label">Supplier quote (₹/tonne, optional)</label><input min="0" type="number" step="0.01" className="field" value={price} readOnly={Boolean(originalPrice)} onChange={(e) => setPrice(e.target.value)} placeholder="Leave blank if unavailable" /></div>
            {price && <div><label className="label">Price valid until</label><input required type="date" className="field" value={priceValidUntil} onChange={(e) => setPriceValidUntil(e.target.value)} /></div>}
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Published source amount (optional)</label><input min="0" type="number" step="0.01" className="field" value={originalPrice} onChange={(e) => {
                setOriginalPrice(e.target.value)
                setPrice(e.target.value ? String(Number(e.target.value) * (originalPriceUnit === 'INR/kg' ? 1000 : 1)) : '')
              }} /></div>
              <div><label className="label">Published source unit</label><select className="field" value={originalPriceUnit} onChange={(e) => {
                setOriginalPriceUnit(e.target.value)
                if (originalPrice) setPrice(String(Number(originalPrice) * (e.target.value === 'INR/kg' ? 1000 : 1)))
              }}><option value="INR/tonne">₹/tonne</option><option value="INR/kg">₹/kg</option></select></div>
            </div>
            {price && <>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="label">GST rate (%)</label><input min="0" max="100" type="number" step="0.01" className="field" value={gstRate} onChange={(e) => setGstRate(e.target.value)} placeholder="Optional" /></div>
                <div><label className="label">GST price treatment</label><select className="field" value={gstInclusive} onChange={(e) => setGstInclusive(e.target.value)}><option value="">Not specified</option><option value="true">Inclusive</option><option value="false">Exclusive</option></select></div>
              </div>
              <div><label className="label">Quote source organization</label><input required className="field" value={priceSourceOrg} onChange={(e) => setPriceSourceOrg(e.target.value)} /></div>
              <div><label className="label">Quote/source title</label><input required className="field" value={priceSourceTitle} onChange={(e) => setPriceSourceTitle(e.target.value)} /></div>
              <div><label className="label">Quote source URL</label><input required type="url" className="field" value={priceSourceUrl} onChange={(e) => setPriceSourceUrl(e.target.value)} /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="label">Publication date (if applicable)</label><input type="date" className="field" value={pricePublicationDate} onChange={(e) => setPricePublicationDate(e.target.value)} /></div>
                <div><label className="label">Geographic coverage</label><input required className="field" value={priceCoverage} onChange={(e) => setPriceCoverage(e.target.value)} placeholder="Supplier / city / region" /></div>
              </div>
              <div><label className="label">Date received/retrieved</label><input required type="date" className="field" value={priceRetrievedDate} onChange={(e) => setPriceRetrievedDate(e.target.value)} /></div>
              <div><label className="label">Grade / quality</label><input required className="field" value={priceGrade} onChange={(e) => setPriceGrade(e.target.value)} /></div>
              <div><label className="label">Quote limitations</label><textarea className="field min-h-16" value={priceLimitations} onChange={(e) => setPriceLimitations(e.target.value)} /></div>
              <p className="text-xs text-slate-500">Supplier-entered market quote; not an official published price. No conversion from legacy currencies is performed.</p>
            </>}
            <div><label className="label">Public summary</label><textarea required className="field min-h-20" value={publicSummary} onChange={(e) => setPublicSummary(e.target.value)} /></div>
            <div><label className="label">Status</label><select className="field" value={status} onChange={(e) => setStatus(e.target.value)}><option value="available">Available</option><option value="reserved">Reserved</option></select></div>
            {message && <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
            <button type="submit" className="primary-btn w-full">Publish listing</button>
          </form>
        </div>
      </div>
    </main>
  )
}

function MarketplacePage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Material[]>([])
  const [message, setMessage] = useState('')
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [filters, setFilters] = useState({ state: '', city: '', category: '', price_available: '', verification_status: '' })

  useEffect(() => {
    if (token) {
      apiRequest<{ user: User }>('/auth/me', 'GET', token)
        .then((data) => setCurrentUser(data.user))
        .catch((e) => setMessage(e.message))
    }
  }, [token])

  useEffect(() => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value)
    })
    apiRequest<{ items: Material[] }>(`/marketplace${params.size ? `?${params.toString()}` : ''}`, 'GET', token ?? undefined)
      .then((result) => setItems(result.items))
      .catch((e) => setMessage(e.message))
  }, [token, filters])

  const requestAccess = async (listingId: number) => {
    try {
      await apiRequest('/access-requests', 'POST', token ?? undefined, {
        listing_id: listingId,
        reason: 'Need confidential details for a sustainability and reuse evaluation.',
      })
      setMessage('Access request sent to owner.')
    } catch (e) {
      setMessage((e as Error).message)
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <h1 className="text-3xl font-bold text-slate-900">Marketplace</h1>
      {message && <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
      <div className="mt-6 grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-5">
        <select className="field" aria-label="Filter by Indian state" value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
          <option value="">All states</option>{INDIAN_STATES.map((value) => <option key={value}>{value}</option>)}
        </select>
        <input className="field" aria-label="Filter by city" placeholder="City (e.g. Hyderabad)" value={filters.city} onChange={(e) => setFilters({ ...filters, city: e.target.value })} />
        <select className="field" aria-label="Filter by material category" value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })}>
          <option value="">All categories</option>{CATEGORIES.map((value) => <option key={value}>{value}</option>)}
        </select>
        <select className="field" aria-label="Filter by price availability" value={filters.price_available} onChange={(e) => setFilters({ ...filters, price_available: e.target.value })}>
          <option value="">Any price status</option><option value="true">INR quote available</option><option value="false">Price unavailable</option>
        </select>
        <select className="field" aria-label="Filter by verification status" value={filters.verification_status} onChange={(e) => setFilters({ ...filters, verification_status: e.target.value })}>
          <option value="">Any verification</option><option value="verified">Verified</option><option value="pending">Pending</option><option value="unverified">Unverified</option><option value="rejected">Rejected</option>
        </select>
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <div key={item.id} className="card p-5">
            <div className="flex items-center justify-between"><span className="badge">{item.category}</span><span className="text-sm text-slate-500">{item.material_type}</span></div>
            <h2 className="mt-4 text-xl font-semibold">{item.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{item.public_summary}</p>
            <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
              <div>{formatIndianNumber(item.quantity)} {item.unit}</div>
              <div>{item.city && item.state ? `${item.city}, ${item.state}` : item.location}</div>
              <div className="mt-2 font-semibold">{item.price_available && item.currency_code === 'INR' && item.price_per_ton != null ? formatINRPerTonne(item.price_per_ton) : 'Price unavailable — request a supplier quotation'}</div>
              {item.price_available && item.price_original_amount !== null && item.price_original_currency_code === 'INR' && <div className="text-xs text-slate-500">Source amount: {item.price_original_unit === 'INR/tonne' ? formatINRPerTonne(item.price_original_amount) : `${formatINR(item.price_original_amount)} / ${item.price_original_unit}`}</div>}
              {item.price_available && item.price_original_amount !== null && item.price_original_currency_code !== 'INR' && <div className="text-xs text-slate-500">Original source amount not displayed as INR (currency: {item.price_original_currency_code ?? 'unknown'}).</div>}
              {item.price_available && <div className="text-xs">GST {item.gst_inclusive === null ? 'treatment not specified' : item.gst_inclusive ? 'inclusive' : 'exclusive'}{item.gst_rate_percent !== null ? ` · ${item.gst_rate_percent}%` : ''}</div>}
              {item.price_source_title && <div className="text-xs text-slate-500">{item.price_source_org}: {item.price_source_title}</div>}
              {item.price_source_url && <a className="mt-1 inline-block text-xs text-emerald-700 underline" href={item.price_source_url} target="_blank" rel="noreferrer">Price source</a>}
              {item.price_publication_date && <div className="text-xs text-slate-500">Published {item.price_publication_date}</div>}
              {item.price_retrieved_date && <div className="text-xs text-slate-500">Received/retrieved {item.price_retrieved_date}</div>}
              {item.price_geographic_coverage && <div className="text-xs text-slate-500">Coverage: {item.price_geographic_coverage}{item.price_grade ? ` · Grade: ${item.price_grade}` : ''}</div>}
              {item.price_limitations && <div className="text-xs text-slate-500">Limitations: {item.price_limitations}</div>}
              {item.price_last_updated && <div className="text-xs text-slate-500">Price last updated {item.price_last_updated}</div>}
              {item.price_valid_until && <div className="text-xs">Price status: {item.price_status} · Valid until {item.price_valid_until}</div>}
              {item.price_available && <div className="text-xs">Supplier-price verification: {item.price_verification_status === 'verified' && item.demo_label !== 'DEMONSTRATION DATA' ? 'verified' : item.demo_label === 'DEMONSTRATION DATA' ? 'demonstration data — not verified' : 'unverified supplier quote'}</div>}
              <div className="mt-1 text-xs">Verification: {item.verification_status}</div>
              <div className="mt-2 text-xs font-semibold text-amber-700">{item.demo_label}</div>
            </div>
            <QuotationRequestAction item={item} token={token} canRequest={currentUser?.role === 'seeker' || currentUser?.role === 'admin'} />
            <button className="primary-btn mt-4 w-full" onClick={() => requestAccess(item.id)}>Request access</button>
          </div>
        ))}
      </div>
    </main>
  )
}

function RequirementsPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Requirement[]>([])
  const [title, setTitle] = useState('Cement replacement requirement')
  const [materialCategory, setMaterialCategory] = useState('Fly ash')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('tonnes')
  const [city, setCity] = useState('Hyderabad')
  const [state, setState] = useState('Telangana')
  const [notes, setNotes] = useState('Low moisture, suitable for ready-mix concrete.')
  const [message, setMessage] = useState('')

  const load = useCallback(() => {
    apiRequest<{ items: Requirement[] }>('/requirements', 'GET', token ?? undefined)
      .then((result) => setItems(result.items))
      .catch((e) => setMessage(e.message))
  }, [token])

  useEffect(() => { load() }, [load])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await apiRequest('/requirements', 'POST', token ?? undefined, {
        title, material_category: materialCategory, quantity: Number(quantity), unit, city, state, technical_specs: notes,
      })
      setMessage('Requirement submitted successfully.')
      load()
    } catch (e) {
      setMessage((e as Error).message)
    }
  }

  const runMatching = async (id: number) => {
    try {
      const result = await apiRequest<{ items: Array<Record<string, unknown>> }>('/matches', 'POST', token ?? undefined, { requirement_id: id })
      setMessage(`Generated ${result.items.length} match recommendations.`)
    } catch (e) {
      setMessage((e as Error).message)
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="card p-6">
          <h1 className="text-2xl font-bold text-slate-900">Requirements and matching</h1>
          <div className="mt-5 space-y-4">
            {items.map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="font-semibold text-slate-900">{item.title}</h2>
                  <button className="secondary-btn" onClick={() => runMatching(item.id)}>Generate matches</button>
                </div>
                <div className="mt-2 text-sm text-slate-600">{item.material_category} · {formatIndianNumber(item.quantity)} {item.unit} · {item.city && item.state ? `${item.city}, ${item.state}` : item.location}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-6">
          <h2 className="text-xl font-semibold">New requirement</h2>
          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div><label className="label">Title</label><input className="field" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><label className="label">Material category</label><select className="field" value={materialCategory} onChange={(e) => setMaterialCategory(e.target.value)}>{['Fly ash', 'Rice husk ash', 'Steel scrap', 'Aluminium scrap', 'Sawdust', 'Textile waste', 'Glass waste', 'Plastic production scrap'].map((value) => <option key={value}>{value}</option>)}</select></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Quantity</label><input required min="0.001" step="any" type="number" className="field" value={quantity} onChange={(e) => setQuantity(e.target.value)} /></div>
              <div><label className="label">Unit</label><select className="field" value={unit} onChange={(e) => setUnit(e.target.value)}><option value="tonnes">tonnes</option><option value="kg">kg</option></select></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">State</label><select className="field" value={state} onChange={(e) => setState(e.target.value)}>{INDIAN_STATES.map((value) => <option key={value}>{value}</option>)}</select></div>
              <div><label className="label">City</label><input required className="field" value={city} onChange={(e) => setCity(e.target.value)} /></div>
            </div>
            <div><label className="label">Technical specs</label><textarea className="field min-h-24" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
            {message && <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
            <button type="submit" className="primary-btn w-full">Save requirement</button>
          </form>
        </div>
      </div>
    </main>
  )
}

function MatchResultsPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])
  const [currentUser, setCurrentUser] = useState<User | null>(null)

  useEffect(() => {
    apiRequest<{ items: Array<Record<string, unknown>> }>('/matches', 'GET', token ?? undefined)
      .then((result) => setItems(result.items))
      .catch(() => setItems([]))
  }, [token])

  useEffect(() => {
    if (token) apiRequest<{ user: User }>('/auth/me', 'GET', token).then((result) => setCurrentUser(result.user)).catch(() => setCurrentUser(null))
  }, [token])

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <h1 className="text-3xl font-bold text-slate-900">Matching results</h1>
      <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item: any) => (
          <div key={item.id} className="card p-5">
            <div className="text-sm text-slate-500">Score</div>
            <div className="mt-2 text-4xl font-bold text-emerald-700">{item.score}</div>
            <div className="mt-4 text-lg font-semibold">{item.listing?.title}</div>
            <div className="mt-2 text-sm text-slate-600">{item.reasons}</div>
            <div className="mt-2 text-sm font-medium">{item.listing?.price_available && item.listing?.currency_code === 'INR' && typeof item.listing?.price_per_ton === 'number' ? formatINRPerTonne(item.listing.price_per_ton) : 'Price unavailable — request a supplier quotation'}</div>
            {item.listing?.price_available && <div className="mt-1 text-xs text-slate-500">{item.listing.price_verification_status === 'verified' && item.listing.demo_label !== 'DEMONSTRATION DATA' ? 'Verified supplier price' : item.listing.demo_label === 'DEMONSTRATION DATA' ? 'Demonstration price — not verified' : 'Unverified supplier quotation'}{item.listing.price_valid_until ? ` · Valid until ${item.listing.price_valid_until}` : ''}</div>}
            {item.listing?.demo_label && <div className="mt-2 text-xs font-semibold text-amber-700">{item.listing.demo_label}</div>}
            {item.listing && <QuotationRequestAction item={item.listing} token={token} canRequest={currentUser?.role === 'seeker' || currentUser?.role === 'admin'} />}
            <Link to={`/matches/${item.id}`} className="primary-btn mt-4 w-full">View details</Link>
          </div>
        ))}
      </div>
    </main>
  )
}

function MatchDetailPage({ token }: { token: string | null }) {
  const { id } = useParams()
  const [detail, setDetail] = useState<any>(null)
  const [currentUser, setCurrentUser] = useState<User | null>(null)

  useEffect(() => {
    if (!id) return
    apiRequest<{ items: Array<Record<string, unknown>> }>('/matches', 'GET', token ?? undefined)
      .then((result) => setDetail(result.items.find((item: any) => String(item.id) === id) ?? null))
      .catch(() => setDetail(null))
  }, [id, token])

  useEffect(() => {
    if (token) apiRequest<{ user: User }>('/auth/me', 'GET', token).then((result) => setCurrentUser(result.user)).catch(() => setCurrentUser(null))
  }, [token])

  if (!detail) return <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">No match details available.</main>

  return (
    <main className="mx-auto max-w-4xl px-4 py-10 lg:px-8">
      <div className="card p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-slate-900">{detail.listing?.title}</h1>
          <span className="badge">{detail.score}/100</span>
        </div>
        <p className="mt-4 text-slate-600">{detail.reasons}</p>
        <div className="mt-4 font-medium">{detail.listing?.price_available && detail.listing?.currency_code === 'INR' && typeof detail.listing?.price_per_ton === 'number' ? formatINRPerTonne(detail.listing.price_per_ton) : 'Price unavailable — request a supplier quotation'}</div>
        {detail.listing?.price_available && <div className="mt-1 text-xs text-slate-500">{detail.listing.price_verification_status === 'verified' && detail.listing.demo_label !== 'DEMONSTRATION DATA' ? 'Verified supplier price' : detail.listing.demo_label === 'DEMONSTRATION DATA' ? 'Demonstration price — not verified' : 'Unverified supplier quotation'}{detail.listing.price_valid_until ? ` · Valid until ${detail.listing.price_valid_until}` : ''}</div>}
        {detail.listing?.demo_label && <div className="mt-2 text-xs font-semibold text-amber-700">{detail.listing.demo_label}</div>}
        {detail.listing && <QuotationRequestAction item={detail.listing} token={token} canRequest={currentUser?.role === 'seeker' || currentUser?.role === 'admin'} />}
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 p-4"><div className="text-sm text-slate-500">Breakdown</div><div className="mt-2 text-slate-700">{detail.breakdown || 'No breakdown supplied.'}</div></div>
          <div className="rounded-2xl border border-slate-200 p-4"><div className="text-sm text-slate-500">Warnings</div><div className="mt-2 text-slate-700">{detail.warnings || 'No warnings in this demo scenario.'}</div></div>
        </div>
      </div>
    </main>
  )
}

function VerificationPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])
  const [listingId, setListingId] = useState('1')
  const [propertyName, setPropertyName] = useState('general review')
  const [status, setStatus] = useState('approved')
  const [notes, setNotes] = useState('Review approved for demonstration use.')
  const [evidenceUrl, setEvidenceUrl] = useState('')

  const load = useCallback(() => {
    apiRequest<{ items: Array<Record<string, unknown>> }>('/verification', 'GET', token ?? undefined)
      .then((result) => setItems(result.items))
      .catch(() => setItems([]))
  }, [token])

  useEffect(() => { load() }, [load])

  const submitReview = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await apiRequest(`/verification/${listingId}/review`, 'POST', token ?? undefined, {
      property_name: propertyName,
      status,
      notes,
      evidence_url: evidenceUrl,
    })
    load()
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="card p-6">
          <h1 className="text-2xl font-bold text-slate-900">Verification centre</h1>
          <div className="mt-5 space-y-4">
            {items.map((item: any) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between"><div className="font-semibold">{item.listing_title}</div><span className="badge">{item.status}</span></div>
                <div className="mt-2 text-sm text-slate-600">{item.property_name}: {item.notes}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-6">
          <h2 className="text-xl font-semibold">Submit review</h2>
          <form className="mt-4 space-y-4" onSubmit={submitReview}>
            <div><label className="label">Listing ID</label><input className="field" value={listingId} onChange={(e) => setListingId(e.target.value)} /></div>
            <div><label className="label">Review area</label><select className="field" value={propertyName} onChange={(e) => setPropertyName(e.target.value)}><option value="general review">General listing</option><option value="price quotation">Price quotation</option></select></div>
            <div><label className="label">Status</label><select className="field" value={status} onChange={(e) => setStatus(e.target.value)}><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="pending">Pending</option></select></div>
            <div><label className="label">Notes</label><textarea className="field min-h-24" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
            <div><label className="label">Evidence URL (required before listing can be marked verified)</label><input type="url" className="field" value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} /></div>
            <button type="submit" className="primary-btn w-full">Save review</button>
          </form>
        </div>
      </div>
    </main>
  )
}

function PrivacyPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])

  useEffect(() => {
    apiRequest<{ items: Array<Record<string, unknown>> }>('/access-requests', 'GET', token ?? undefined)
      .then((result) => setItems(result.items))
      .catch(() => setItems([]))
  }, [token])

  const decide = async (id: number, decision: 'approved' | 'rejected') => {
    await apiRequest(`/access-requests/${id}/decision`, 'POST', token ?? undefined, { decision })
    const next = await apiRequest<{ items: Array<Record<string, unknown>> }>('/access-requests', 'GET', token ?? undefined)
    setItems(next.items)
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="card p-6">
        <div className="flex items-center gap-3"><Lock className="h-6 w-6 text-emerald-700" /><h1 className="text-2xl font-bold text-slate-900">Privacy and access requests</h1></div>
        <div className="mt-6 space-y-4">
          {items.map((item: any) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-semibold">Request for {item.listing_title}</div>
                  <div className="text-sm text-slate-600">{item.reason}</div>
                </div>
                <div className="badge">{item.status}</div>
              </div>
              <div className="mt-4 flex gap-3">
                <button className="primary-btn" onClick={() => decide(item.id, 'approved')}>Approve</button>
                <button className="secondary-btn" onClick={() => decide(item.id, 'rejected')}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}

function ImpactCalculatorPage({ token }: { token: string | null }) {
  const [form, setForm] = useState({
    mass: '',
    mass_unit: 'tonnes',
    distance_km: '',
    electricity_kwh: '',
    material_type: 'Fly ash',
    transport_cost_inr_per_tonne_km: '',
    processing_cost_inr_per_tonne: '',
    avoided_disposal_savings_inr_per_tonne: '',
    material_purchase_cost_inr_per_tonne: '',
  })
  const [factors, setFactors] = useState<Array<Record<string, any>>>([])
  const [selectedFactors, setSelectedFactors] = useState<Record<string, string>>({})
  const [result, setResult] = useState<{ status: string; message: string; result: Record<string, any> | null } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<{ items: Array<Record<string, any>> }>('/emission-factors', 'GET', token ?? undefined)
      .then((data) => setFactors(data.items))
      .catch((e) => setError(e.message))
  }, [token])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    try {
      const factorIds = Object.fromEntries(
        Object.entries(selectedFactors)
          .filter(([, id]) => id)
          .map(([key, id]) => [key, Number(id)]),
      )
      const monetaryInputs = Object.fromEntries(
        Object.entries(form)
          .filter(([key]) => key.endsWith('_inr_per_tonne') || key.endsWith('_inr_per_tonne_km'))
          .filter(([, value]) => value !== '')
          .map(([key, value]) => [key, Number(value)]),
      )
      const data = await apiRequest<{ status: string; message: string; result: Record<string, any> | null }>('/calculator', 'POST', token ?? undefined, {
        ...form,
        mass: Number(form.mass),
        distance_km: Number(form.distance_km),
        electricity_kwh: form.electricity_kwh ? Number(form.electricity_kwh) : undefined,
        factor_ids: factorIds,
        ...monetaryInputs,
      })
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Calculation failed')
    }
  }

  const factorTypes = [
    ['transport', 'Transport (kgCO2e/tonne-km)'],
    ['processing', 'Processing (kgCO2e/tonne)'],
    ['avoided_disposal', 'Avoided disposal (kgCO2e/tonne)'],
    ['virgin_substitution', 'Virgin-material substitution (kgCO2e/tonne)'],
    ['grid_electricity', 'CEA/grid electricity (kgCO2e/kWh)'],
  ]

  const displayImpact = (value: unknown) => value === null || value === undefined ? 'Insufficient data' : `${formatIndianNumber(Number(value))} kgCO2e`
  const displayCost = (value: unknown) => value === null || value === undefined ? 'Insufficient data' : formatINR(Number(value))

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="card p-6">
          <h1 className="text-2xl font-bold text-slate-900">India impact calculator</h1>
          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div><label className="label">Material type</label><input className="field" value={form.material_type} onChange={(e) => setForm({ ...form, material_type: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Mass</label><input required min="0.001" step="any" className="field" type="number" value={form.mass} onChange={(e) => setForm({ ...form, mass: e.target.value })} /></div>
              <div><label className="label">Mass unit</label><select className="field" value={form.mass_unit} onChange={(e) => setForm({ ...form, mass_unit: e.target.value })}><option value="tonnes">tonnes</option><option value="kg">kg</option></select></div>
            </div>
            <div><label className="label">Transport distance (km)</label><input required min="0" step="any" className="field" type="number" value={form.distance_km} onChange={(e) => setForm({ ...form, distance_km: e.target.value })} /></div>
            <h2 className="pt-2 font-semibold">Verified emissions factors</h2>
            {factorTypes.map(([key, label]) => {
              const options = factors.filter((factor) => factor.factor_type === key && factor.verification_status === 'verified')
              return <div key={key}>
                <label className="label">{label}</label>
                <select className="field" value={selectedFactors[key] ?? ''} onChange={(e) => setSelectedFactors({ ...selectedFactors, [key]: e.target.value })}>
                  <option value="">No verified factor available</option>
                  {options.map((factor) => <option key={factor.id} value={factor.id}>{factor.name} · {factor.reporting_year} · {factor.source_org}</option>)}
                </select>
              </div>
            })}
            {selectedFactors.grid_electricity && <div><label className="label">Processing electricity (kWh)</label><input min="0" step="any" className="field" type="number" value={form.electricity_kwh} onChange={(e) => setForm({ ...form, electricity_kwh: e.target.value })} /></div>}
            <h2 className="pt-2 font-semibold">Optional supplier/economic inputs (INR)</h2>
            <div><label className="label">Transport cost (₹/tonne-km)</label><input min="0" step="any" className="field" type="number" value={form.transport_cost_inr_per_tonne_km} onChange={(e) => setForm({ ...form, transport_cost_inr_per_tonne_km: e.target.value })} /></div>
            <div><label className="label">Processing cost (₹/tonne)</label><input min="0" step="any" className="field" type="number" value={form.processing_cost_inr_per_tonne} onChange={(e) => setForm({ ...form, processing_cost_inr_per_tonne: e.target.value })} /></div>
            <div><label className="label">Avoided disposal saving (₹/tonne)</label><input min="0" step="any" className="field" type="number" value={form.avoided_disposal_savings_inr_per_tonne} onChange={(e) => setForm({ ...form, avoided_disposal_savings_inr_per_tonne: e.target.value })} /></div>
            <div><label className="label">Material purchase cost (₹/tonne)</label><input min="0" step="any" className="field" type="number" value={form.material_purchase_cost_inr_per_tonne} onChange={(e) => setForm({ ...form, material_purchase_cost_inr_per_tonne: e.target.value })} /></div>
            <p className="text-xs text-slate-500">A CEA FY 2022-23 factor was cited in the request, but the guide redirects to a login page. It is recorded as source-claimed and is not available as a verified calculator factor.</p>
            {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
            <button type="submit" className="primary-btn w-full">Calculate impact</button>
          </form>
        </div>
        <div className="card p-6">
          <h2 className="text-xl font-semibold">Results (estimate, not an independent verification)</h2>
          {result ? (
            <div className="mt-5 space-y-4">
              <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{result.message}</p>
              {result.result && <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Transport emissions</div><div className="mt-1 font-semibold">{displayImpact(result.result.transport_emissions_kgco2e)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Processing emissions</div><div className="mt-1 font-semibold">{displayImpact(result.result.processing_emissions_kgco2e)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Avoided disposal emissions</div><div className="mt-1 font-semibold">{displayImpact(result.result.avoided_disposal_kgco2e)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Virgin-material substitution</div><div className="mt-1 font-semibold">{displayImpact(result.result.virgin_substitution_kgco2e)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Net GHG benefit</div><div className="mt-1 text-xl font-bold text-emerald-700">{displayImpact(result.result.net_emissions_benefit_kgco2e)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Net economic benefit</div><div className="mt-1 text-xl font-bold text-emerald-700">{displayCost(result.result.net_economic_benefit_inr)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Transport cost</div><div className="mt-1 font-semibold">{displayCost(result.result.transport_cost_inr)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Processing cost</div><div className="mt-1 font-semibold">{displayCost(result.result.processing_cost_inr)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Avoided disposal savings</div><div className="mt-1 font-semibold">{displayCost(result.result.avoided_disposal_savings_inr)}</div></div>
                  <div className="rounded-xl bg-slate-50 p-3"><div className="text-sm text-slate-500">Material purchase cost</div><div className="mt-1 font-semibold">{displayCost(result.result.material_purchase_cost_inr)}</div></div>
                </div>
                <div className="text-xs text-slate-500">Factor reporting year(s): {result.result.reporting_years?.join(', ') || 'none'} · {result.result.assumptions}</div>
                {Object.entries(result.result.factors ?? {}).map(([key, factor]: [string, any]) => (
                  <div key={key} className="rounded-xl border border-slate-200 p-3 text-xs text-slate-600">
                    <div className="font-semibold">{factor.source_org}: {factor.source_title} ({factor.reporting_year})</div>
                    <div>{key} · {factor.value} {factor.unit} · Retrieved {factor.retrieved_date}</div>
                    <a className="text-emerald-700 underline" href={factor.source_url} target="_blank" rel="noreferrer">View source</a>
                    {factor.assumptions && <div>Assumptions: {factor.assumptions}</div>}
                    {factor.methodology && <div>Methodology: {factor.methodology}</div>}
                    {factor.limitations && <div>Limitations: {factor.limitations}</div>}
                  </div>
                ))}
              </>}
            </div>
          ) : (
            <div className="mt-5 text-slate-500">No estimate generated yet.</div>
          )}
        </div>
      </div>
      <DataSourcesSection className="mt-6" />
    </main>
  )
}

function AnalyticsPage({ token }: { token: string | null }) {
  const [data, setData] = useState<any>(null)
  useEffect(() => {
    apiRequest<{ metrics: Record<string, number>; labels: string[]; series: number[] }>('/analytics', 'GET', token ?? undefined)
      .then((result) => setData(result))
      .catch(() => setData(null))
  }, [token])

  const chartData = useMemo<Array<{ label: string; value: number }>>(() => {
    if (!data) return []
    return data.labels.map((label: string, index: number) => ({ label, value: data.series[index] }))
  }, [data])

  const colors = ['#0f766e', '#14b8a6', '#2dd4bf', '#34d399', '#10b981']

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <h1 className="text-3xl font-bold text-slate-900">Circular economy analytics</h1>
      {data && (
        <>
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <div className="card p-5"><div className="text-sm text-slate-500">Public listings</div><div className="mt-2 text-2xl font-bold">{formatIndianNumber(data.metrics.public_materials)}</div></div>
          <div className="card p-5"><div className="text-sm text-slate-500">Available mass</div><div className="mt-2 text-2xl font-bold">{formatIndianNumber(data.metrics.quantity_tonnes)} tonnes</div></div>
          <div className="card p-5"><div className="text-sm text-slate-500">Requirements</div><div className="mt-2 text-2xl font-bold">{formatIndianNumber(data.metrics.requirements)}</div></div>
          <div className="card p-5"><div className="text-sm text-slate-500">Average match score</div><div className="mt-2 text-2xl font-bold">{formatIndianNumber(data.metrics.avg_match_score)}</div></div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <div className="card p-6">
            <div className="mb-4 text-lg font-semibold">By-product opportunity mix</div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip formatter={(value) => [`${formatIndianNumber(Number(value))} tonnes`, 'Available mass']} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} fill="#0f766e" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card p-6">
            <div className="mb-4 text-lg font-semibold">Distribution</div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={chartData} dataKey="value" nameKey="label" innerRadius={50} outerRadius={90} paddingAngle={3}>
                    {chartData.map((entry, index: number) => <Cell key={String(entry.label ?? index)} fill={colors[index % colors.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value) => [`${formatIndianNumber(Number(value))} tonnes`, 'Available mass']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        </>
      )}
    </main>
  )
}

function AdminReviewPage({ token }: { token: string | null }) {
  const [data, setData] = useState<any>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [factorMessage, setFactorMessage] = useState('')
  const [factorForm, setFactorForm] = useState({
    factor_type: 'grid_electricity',
    name: '',
    value: '',
    source_org: '',
    source_title: '',
    source_url: '',
    publication_date: '',
    retrieved_date: '',
    geographic_coverage: 'India',
    reporting_year: '',
    assumptions: '',
    methodology: '',
    limitations: '',
    verification_status: 'unverified',
  })
  useEffect(() => {
    apiRequest<{ requests: Array<Record<string, unknown>>; audit_events: Array<Record<string, unknown>> }>('/admin/review', 'GET', token ?? undefined)
      .then((result) => setData(result))
      .catch(() => setData(null))
    apiRequest<{ user: User }>('/auth/me', 'GET', token ?? undefined)
      .then((result) => setIsAdmin(result.user.role === 'admin'))
      .catch(() => setIsAdmin(false))
  }, [token])

  const addFactor = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const unit = factorForm.factor_type === 'grid_electricity'
      ? 'kgCO2e/kWh'
      : factorForm.factor_type === 'transport'
        ? 'kgCO2e/tonne-km'
        : 'kgCO2e/tonne'
    try {
      const result = await apiRequest<{ item: { id: number } }>('/emission-factors', 'POST', token ?? undefined, {
        ...factorForm,
        value: Number(factorForm.value),
        reporting_year: Number(factorForm.reporting_year),
        unit,
      })
      setFactorMessage(`Factor ${result.item.id} saved as ${factorForm.verification_status}.`)
    } catch (e) {
      setFactorMessage(e instanceof Error ? e.message : 'Unable to save factor')
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 lg:px-8">
      <div className="card p-6">
        <h1 className="text-3xl font-bold text-slate-900">Admin review panel</h1>
        {data && (
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div>
              <div className="mb-3 text-lg font-semibold">Access requests</div>
              {data.requests.map((item: any) => (
                <div key={item.id} className="mb-3 rounded-xl border border-slate-200 p-3">
                  <div className="font-medium">{item.listing}</div>
                  <div className="text-sm text-slate-600">{item.status}</div>
                </div>
              ))}
            </div>
            <div>
              <div className="mb-3 text-lg font-semibold">Audit trail</div>
              {data.audit_events.map((item: any) => (
                <div key={item.id} className="mb-3 rounded-xl border border-slate-200 p-3">
                  <div className="font-medium">{item.action}</div>
                  <div className="text-sm text-slate-600">{item.details}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {isAdmin && <div className="card mt-6 p-6">
        <h2 className="text-xl font-semibold">Add sourced environmental factor</h2>
        <p className="mt-2 text-sm text-slate-600">Enter the exact publication, reporting year, units and limitations. Leave as unverified until evidence has been checked.</p>
        <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={addFactor}>
          <div><label className="label">Factor type</label><select className="field" value={factorForm.factor_type} onChange={(e) => setFactorForm({ ...factorForm, factor_type: e.target.value })}>
            <option value="grid_electricity">Grid electricity</option><option value="transport">Transport</option><option value="processing">Processing</option><option value="avoided_disposal">Avoided disposal</option><option value="virgin_substitution">Virgin-material substitution</option>
          </select></div>
          <div><label className="label">Factor name</label><input required className="field" value={factorForm.name} onChange={(e) => setFactorForm({ ...factorForm, name: e.target.value })} /></div>
          <div><label className="label">Factor value</label><input required min="0" step="any" type="number" className="field" value={factorForm.value} onChange={(e) => setFactorForm({ ...factorForm, value: e.target.value })} /></div>
          <div><label className="label">Source organization</label><input required className="field" value={factorForm.source_org} onChange={(e) => setFactorForm({ ...factorForm, source_org: e.target.value })} /></div>
          <div><label className="label">Source title</label><input required className="field" value={factorForm.source_title} onChange={(e) => setFactorForm({ ...factorForm, source_title: e.target.value })} /></div>
          <div><label className="label">Source URL</label><input required type="url" className="field" value={factorForm.source_url} onChange={(e) => setFactorForm({ ...factorForm, source_url: e.target.value })} /></div>
          <div><label className="label">Publication date</label><input type="date" className="field" value={factorForm.publication_date} onChange={(e) => setFactorForm({ ...factorForm, publication_date: e.target.value })} /></div>
          <div><label className="label">Retrieved date</label><input required type="date" className="field" value={factorForm.retrieved_date} onChange={(e) => setFactorForm({ ...factorForm, retrieved_date: e.target.value })} /></div>
          <div><label className="label">Geographic coverage</label><input required className="field" value={factorForm.geographic_coverage} onChange={(e) => setFactorForm({ ...factorForm, geographic_coverage: e.target.value })} /></div>
          <div><label className="label">Reporting year</label><input required min="1900" max="2100" type="number" className="field" value={factorForm.reporting_year} onChange={(e) => setFactorForm({ ...factorForm, reporting_year: e.target.value })} /></div>
          <div><label className="label">Verification status</label><select className="field" value={factorForm.verification_status} onChange={(e) => setFactorForm({ ...factorForm, verification_status: e.target.value })}><option value="unverified">Unverified</option><option value="pending">Pending</option><option value="verified">Verified</option></select></div>
          <div className="md:col-span-2"><label className="label">Assumptions</label><textarea className="field min-h-16" value={factorForm.assumptions} onChange={(e) => setFactorForm({ ...factorForm, assumptions: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="label">Methodology</label><textarea className="field min-h-16" value={factorForm.methodology} onChange={(e) => setFactorForm({ ...factorForm, methodology: e.target.value })} /></div>
          <div className="md:col-span-2"><label className="label">Limitations</label><textarea className="field min-h-16" value={factorForm.limitations} onChange={(e) => setFactorForm({ ...factorForm, limitations: e.target.value })} /></div>
          {factorMessage && <div className="md:col-span-2 text-sm text-emerald-700">{factorMessage}</div>}
          <button type="submit" className="primary-btn md:col-span-2">Save factor metadata</button>
        </form>
      </div>}
    </main>
  )
}

export default App
