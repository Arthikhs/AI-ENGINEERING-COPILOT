import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Users, Trash2, Loader2, Crown, Code2, Eye } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/utils'
import api from '../services/api'

// API helpers
const getOrgs = () => api.get('/orgs').then(r => r.data)
const createOrg = (name: string, description?: string) =>
  api.post('/orgs', { name, description }).then(r => r.data)
const getMembers = (orgId: string) => api.get(`/orgs/${orgId}/members`).then(r => r.data)
const inviteMember = (orgId: string, username: string, role: string) =>
  api.post(`/orgs/${orgId}/members`, { username, role }).then(r => r.data)
const updateRole = (orgId: string, userId: string, role: string) =>
  api.patch(`/orgs/${orgId}/members/${userId}`, { role }).then(r => r.data)
const removeMember = (orgId: string, userId: string) =>
  api.delete(`/orgs/${orgId}/members/${userId}`).then(r => r.data)
const getOrgRepos = (orgId: string) => api.get(`/orgs/${orgId}/repos`).then(r => r.data)

const ROLE_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  admin:     { label: 'Admin',     color: 'danger',   icon: Crown },
  developer: { label: 'Developer', color: 'info',     icon: Code2 },
  viewer:    { label: 'Viewer',    color: 'default',  icon: Eye },
}

export default function OrganizationsPage() {
  const qc = useQueryClient()
  const [selectedOrg, setSelectedOrg] = useState<any>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [orgName, setOrgName] = useState('')
  const [orgDesc, setOrgDesc] = useState('')
  const [inviteUsername, setInviteUsername] = useState('')
  const [inviteRole, setInviteRole] = useState('developer')
  const [activeTab, setActiveTab] = useState<'members' | 'repos'>('members')

  const { data: orgs = [], isLoading } = useQuery({ queryKey: ['orgs'], queryFn: getOrgs })

  const { data: members = [] } = useQuery({
    queryKey: ['org-members', selectedOrg?.id],
    queryFn: () => getMembers(selectedOrg.id),
    enabled: !!selectedOrg?.id,
  })

  const { data: orgRepos = [] } = useQuery({
    queryKey: ['org-repos', selectedOrg?.id],
    queryFn: () => getOrgRepos(selectedOrg.id),
    enabled: !!selectedOrg?.id && activeTab === 'repos',
  })

  const createMutation = useMutation({
    mutationFn: () => createOrg(orgName, orgDesc),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['orgs'] })
      setShowCreate(false); setOrgName(''); setOrgDesc('')
      setSelectedOrg(data)
    },
  })

  const inviteMutation = useMutation({
    mutationFn: () => inviteMember(selectedOrg.id, inviteUsername, inviteRole),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org-members', selectedOrg.id] })
      setInviteUsername('')
    },
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateRole(selectedOrg.id, userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-members', selectedOrg.id] }),
  })

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeMember(selectedOrg.id, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-members', selectedOrg.id] }),
  })

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Building2 size={22} className="text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Organizations</h1>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} size="sm">
          <Plus size={15} /> New Organization
        </Button>
      </div>

      {/* Create org form */}
      {showCreate && (
        <Card className="mb-6">
          <CardHeader><h2 className="font-semibold text-gray-800">Create Organization</h2></CardHeader>
          <CardContent>
            <div className="flex gap-3 mb-3">
              <input value={orgName} onChange={e => setOrgName(e.target.value)}
                placeholder="Organization name"
                className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <input value={orgDesc} onChange={e => setOrgDesc(e.target.value)}
                placeholder="Description (optional)"
                className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <Button onClick={() => createMutation.mutate()} disabled={!orgName.trim()} loading={createMutation.isPending}>
                Create
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        {isLoading && <div className="col-span-3 flex justify-center py-8"><Loader2 className="animate-spin text-indigo-500" size={20} /></div>}
        {orgs.map((org: any) => (
          <Card key={org.id} onClick={() => setSelectedOrg(org)}
            className={cn('cursor-pointer', selectedOrg?.id === org.id && 'border-indigo-400 shadow-md')}>
            <CardContent className="py-4">
              <div className="flex items-start justify-between mb-2">
                <div className="p-2 bg-indigo-50 rounded-lg">
                  <Building2 size={18} className="text-indigo-600" />
                </div>
                <Badge variant={ROLE_CONFIG[org.role]?.color as any ?? 'default'}>
                  {org.role}
                </Badge>
              </div>
              <p className="font-semibold text-gray-800">{org.name}</p>
              {org.description && <p className="text-xs text-gray-500 mt-1">{org.description}</p>}
              <p className="text-xs text-gray-400 mt-1 font-mono">/{org.slug}</p>
            </CardContent>
          </Card>
        ))}
        {!isLoading && orgs.length === 0 && (
          <div className="col-span-3 text-center py-12 text-gray-400">
            <Building2 size={36} className="mx-auto mb-3 opacity-20" />
            <p>No organizations yet. Create one to get started.</p>
          </div>
        )}
      </div>

      {/* Selected org detail */}
      {selectedOrg && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <Building2 size={18} className="text-indigo-500" />
              {selectedOrg.name}
            </h2>
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
              {(['members', 'repos'] as const).map(t => (
                <button key={t} onClick={() => setActiveTab(t)}
                  className={cn('px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize',
                    activeTab === t ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500')}>
                  {t === 'members' ? <><Users size={12} className="inline mr-1" />Members</> : <>Repositories</>}
                </button>
              ))}
            </div>
          </div>

          {/* Members tab */}
          {activeTab === 'members' && (
            <>
              {/* Invite */}
              {selectedOrg.role === 'admin' && (
                <Card>
                  <CardHeader><h3 className="font-semibold text-gray-800 text-sm">Invite Member</h3></CardHeader>
                  <CardContent>
                    <div className="flex gap-3">
                      <input value={inviteUsername} onChange={e => setInviteUsername(e.target.value)}
                        placeholder="GitHub username"
                        className="flex-1 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                      <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                        className="w-36 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        <option value="admin">Admin</option>
                        <option value="developer">Developer</option>
                        <option value="viewer">Viewer</option>
                      </select>
                      <Button onClick={() => inviteMutation.mutate()} disabled={!inviteUsername.trim()} loading={inviteMutation.isPending}>
                        Invite
                      </Button>
                    </div>
                    {inviteMutation.isSuccess && <p className="text-xs text-green-600 mt-2">✅ Member added</p>}
                    {inviteMutation.isError && <p className="text-xs text-red-600 mt-2">❌ {(inviteMutation.error as any)?.response?.data?.detail}</p>}
                  </CardContent>
                </Card>
              )}

              {/* Member list */}
              <Card>
                <CardHeader>
                  <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                    <Users size={15} /> Members ({members.length})
                  </h3>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {members.map((m: any) => {
                      const RoleIcon = ROLE_CONFIG[m.role]?.icon ?? Code2
                      return (
                        <div key={m.user_id} className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {m.avatar_url
                              ? <img src={m.avatar_url} className="w-8 h-8 rounded-full" alt={m.username} />
                              : <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 text-xs font-bold">{m.username[0].toUpperCase()}</div>}
                            <div>
                              <p className="text-sm font-medium text-gray-800">{m.username}</p>
                              <p className="text-xs text-gray-400">{new Date(m.joined_at).toLocaleDateString()}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {selectedOrg.role === 'admin' ? (
                              <select value={m.role}
                                onChange={e => roleMutation.mutate({ userId: m.user_id, role: e.target.value })}
                                className="text-xs border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                                <option value="admin">Admin</option>
                                <option value="developer">Developer</option>
                                <option value="viewer">Viewer</option>
                              </select>
                            ) : (
                              <Badge variant={ROLE_CONFIG[m.role]?.color as any ?? 'default'}>
                                <RoleIcon size={10} className="mr-1" />{m.role}
                              </Badge>
                            )}
                            {selectedOrg.role === 'admin' && (
                              <button onClick={() => removeMutation.mutate(m.user_id)}
                                className="text-gray-400 hover:text-red-500 transition-colors p-1">
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {/* Repos tab */}
          {activeTab === 'repos' && (
            <Card>
              <CardHeader><h3 className="font-semibold text-gray-800">Organization Repositories ({orgRepos.length})</h3></CardHeader>
              <CardContent>
                {orgRepos.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No repositories in this organization yet.</p>
                  : (
                    <div className="space-y-2">
                      {orgRepos.map((r: any) => (
                        <div key={r.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                          <div>
                            <p className="text-sm font-medium text-gray-800">{r.full_name}</p>
                            <p className="text-xs text-gray-400">{r.total_files} files · {r.total_chunks} chunks</p>
                          </div>
                          <div className="flex items-center gap-2">
                            {r.language && <Badge variant="info">{r.language}</Badge>}
                            <Badge variant={r.is_indexed ? 'success' : 'warning'}>
                              {r.is_indexed ? 'Indexed' : 'Not indexed'}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
