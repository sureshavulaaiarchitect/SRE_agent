import { ReactNode } from 'react'

interface NavItemProps {
  id: string
  icon: ReactNode
  label: string
  active: boolean
  onClick: () => void
}

export const NavItem = ({ id, icon, label, active, onClick }: NavItemProps) => (
  <div 
    className={`nav-item ${active ? 'active' : ''}`}
    onClick={onClick}
    role="button"
    tabIndex={0}
    aria-current={active ? 'page' : undefined}
  >
    {icon}
    <span>{label}</span>
  </div>
)

