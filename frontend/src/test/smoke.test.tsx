import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/KpiCard'

describe('KpiCard', () => {
  it('renderiza label e valor', () => {
    render(<KpiCard label="Enviadas hoje" value="42" hint="atualizado" />)

    expect(screen.getByText('Enviadas hoje')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('atualizado')).toBeInTheDocument()
  })
})
