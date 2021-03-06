#!/usr/bin/env python
# -*- coding: UTF-8 -*-

##@file
# @ingroup python_bindings_examples
# @author Christoph Holtermann (c.holtermann (at) gmx.de)
# @date May 2011
# @brief Exports an invoice to lco-file for use with LaTeX
#
# The output file can be imported into KOMA-Script-letters.
# This works primarily for germany. Internationalization welcome!
#
# Additional files:
#
# - Invoice.tex\n
# Example template file. Should be modified according to personal needs.
# - rechnung.sty\n
# style file for invoices.\n
# This file is not part of the python-bindings!\n
# For an example where to get it see section credits below.
#
# Usage :
# \code latex_invoice file://testfile \endcode
# will create file data.lco.
# \code latex --output-format=pdf Invoice.tex \endcode
# should run latex on file Invoice.tex and result in Invoice.pdf. Invoice.tex includes data.lco.
#
# Additional information :
#
# - http://www.uweziegenhagen.de/latex/documents/rechnung/rechnungen.pdf (german)
# 
# Credits to and ideas from
#
# - Main function as proposed by Guido van Rossum
#   at http://www.artima.com/weblogs/viewpost.jsp?thread=4829
# - Invoice.tex is derived from\n
#   scrlttr2.tex v0.3. (c) by Juergen Fenn <juergen.fenn@gmx.de>\n
#   http://www.komascript.de/node/355\n
#   english translation: ftp://ftp.dante.de/tex-archive/info/templates/fenn/scrlttr2en.tex
# - rechnung.sty\n
#   from M G Berberich (berberic@fmi.uni-passau.de) and Ulrich Sibiller (uli42@web.de)
#   Ver3.10 from http://www.forwiss.uni-passau.de/~berberic/TeX/Rechnung/index.html
#
# To Do:
#
# - get own contact data from gnucash
# - have own bank information in footline
# - nicer formatting of invoice date and date due
# - is there anything else missing in this invoice ?
#
# Changelog:
# MWE: 2014-10-18
#    - resolve compilation errors with and adapted to python 2.7
#    - type error when using 'gnucash.GncNumeric'
#    - resolve error with locales
#    - change commandline switch '-n' (number) to GnuCash invoice ID.
#    - added \usepackage[utf8]{inputenc} to data.lco
#    - amount# use float instead of int (to ensure you can sell eq. 0.75h of hands-on service)
#    - delete input_url from commandline for security reasons
#

latex_filename = "bill.tex"
try:
    import sys
    import getopt
    import gnucash
    from gnucash import GncNumeric
    import str_methods
    ## MWE:2014-10-08 from IPython.Shell import IPShellEmbed
    from IPython.core.interactiveshell import InteractiveShell
    from gnucash.gnucash_business import Customer, Employee, Vendor, Job, \
        Address, Invoice, Entry, TaxTable, TaxTableEntry, GNC_AMT_TYPE_PERCENT, \
            GNC_DISC_PRETAX
    import locale
    import subprocess
except ImportError as import_error:
    print "Problem importing modules."
    print import_error
    sys.exit(2) 

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

def get_all_lots(account):
  """Return all lots in account and descendants"""
  ltotal=[]
  descs = account.get_descendants()
  for desc in descs:
    if type(desc).__name__ == 'SwigPyObject':
        desc = gnucash.Account(instance=desc)
    ll=desc.GetLotList()
    ltotal+=ll
  return ltotal

def get_all_invoices_from_lots(account):
  """Return all invoices in account and descendants

  This is based on lots. So invoices without lots will be missed."""

  lot_list=get_all_lots(account)
  invoice_list=[]
  for lot in lot_list:
    if type(lot).__name__ == 'SwigPyObject':
        lot = gnucash.GncLot(instance=lot)
    invoice=gnucash.gnucash_core_c.gncInvoiceGetInvoiceFromLot(lot.instance)

    if invoice:
      invoice_list.append(Invoice(instance=invoice))
  return invoice_list

def invoice_to_lco(invoice):
  """returns a string which forms a lco-file for use with LaTeX"""

  lco_out=u"\ProvidesFile{data.lco}[]\n\\usepackage[utf8]{inputenc}\n"
  
  def write_variable(ukey, uvalue, replace_linebreak=True):

    outstr = u""
    if uvalue.endswith("\n"):
        uvalue=uvalue[0:len(uvalue)-1]

    if not ukey in [u"fromaddress",u"toaddress",u"date"]:
        outstr += u'\\newkomavar{'
        outstr += ukey
        outstr += u"}\n"

    outstr += u"\\setkomavar{"
    outstr += ukey
    outstr += u"}{"
    if replace_linebreak:
        outstr += uvalue.replace(u"\n",u"\\\\")+"}"
    return outstr

  # Write owners address
  add_str=u""
  owner = invoice.GetOwner()
  if owner.GetName() != "":
    add_str += owner.GetName()+"\n"

  ### MWE: 2014-10-08 double? owner.GetName() vs. addr.GetName()
  #  if addr.GetName() != "":
  #    add_str += addr.GetName().decode("UTF-8")+"\n"
  def mkaddr(addr):
    result = u""
    if addr == None:
        return u""
    if addr.GetAddr1() != "":
      result += addr.GetAddr1().decode("UTF-8")+"\n"
    if addr.GetAddr2() != "":
      result += addr.GetAddr2().decode("UTF-8")+"\n"
    if addr.GetAddr3() != "":
      result += addr.GetAddr3().decode("UTF-8")+"\n"
    if addr.GetAddr4() != "":
      result += addr.GetAddr4().decode("UTF-8")+"\n"
    return result
  add_str += mkaddr(owner.GetAddr())

  lco_out += write_variable("toaddress2",add_str)

  # Invoice number
  inr_str = invoice.GetID()
  lco_out += write_variable("rechnungsnummer",inr_str)

  # date
  date      = invoice.GetDatePosted()
  udate     = date.strftime("%d.%m.%Y")
  lco_out  += write_variable("date",udate)+"\n"

  # date due
  date_due  = invoice.GetDateDue()
  udate_due = date_due.strftime("%d.%m.%Y")
  lco_out  += write_variable("date_due",udate_due)+"\n"
  lco_out += write_variable("description", str(invoice.GetNotes()))

  # Write the entries
  ent_str = u""
  ### MWE: locale.setlocale(locale.LC_ALL,"de_DE")
  taxes = 0.0
  bruto = 0.0
  total = 0.0
  for n,ent in enumerate(invoice.GetEntries()): 
      
      line_str = u""

      if type(ent) != Entry:
        ent=Entry(instance=ent)                                 # Add to method_returns_list
      
      descr = ent.GetDescription()
      ### MWE: 2014-10-08 type error when using 'gnucash.GncNumeric'
      price = gnucash.gnucash_core_c._gnc_numeric()
      price = ent.GetInvPrice().to_double()

      taxval = ent.GetDocTaxValue(True,True,False)

      n     = gnucash.gnucash_core_c._gnc_numeric()
      n     = instance=ent.GetQuantity()                        # change gncucash_core.py
      locale.setlocale( locale.LC_ALL, '' )
      uprice = locale.currency(price/1.21).rstrip(" EUR").rstrip(" €").strip("€ ")
      ### MWE: 2014-10-08 use float instead of int. 
      ###      Otherwise decimal places will be cut and nobody want to spend 0.75 h for nothing but stupid software.
      quantity = float(n.num())/n.denom()
      un = unicode(quantity)               # choose best way to format numbers according to locale

      curtaxes = GncNumeric(taxval.num, taxval.denom).to_double()
      curprice = price*quantity
      taxes += curtaxes
      total += curprice
      bruto += curprice - curtaxes

      line_str =  u"\Artikel{"
      line_str += un
      line_str += u"}{"
      line_str += descr.decode("UTF-8")
      line_str += u"}{"

      line_str += uprice
      line_str += u"}"
      print(ent.GetAction())
      # Perhaps to add the action table??
      line_str += u"{"
      line_str += "uur" if ent.GetAction() == "Uren"  else "art."
      line_str += u"}"
      #print line_str
      ent_str += line_str

  lco_out += write_variable("taxes", str(round(taxes,2)))
  lco_out += write_variable("bruto", str(round(bruto,2)))
  lco_out += write_variable("total", str(round(total,2)))
  lco_out += write_variable("entries",ent_str)

  return lco_out


def main(argv=None):
    print "start"
    if argv is None:
        argv = sys.argv
    try:
        input_url = "file:///home/jappie/Documents/company/boekhouding/boekhouding.gnucash"
        prog_name = argv[0]
        with_ipshell = False
        ignore_lock = False
        no_latex_output = False
        list_invoices = False
        output_file_name = "data.lco"
        invoice_number = None

        try:
            ## MWE: 2014-10-06 opts, args = getopt.getopt(argv[1:], "fhiln:po:", ["help"])
            opts, args = getopt.getopt(argv[1:], "fhiln:po:", ["help"])
        except getopt.error, msg:
             raise Usage(msg)
        
        for opt in opts:
            if opt[0] in ["-f"]:
                print "ignoring lock"
                ignore_lock = True
            if opt[0] in ["-h","--help"]:
                raise Usage("Help:")
            if opt[0] in ["-i"]:
                print "Using ipshell"
                with_ipshell = True
            if opt[0] in ["-l"]:
                print "listing all invoices"
                list_invoices=True
            if opt[0] in ["-n"]:
                invoice_number = opt[1]
                print "using invoice number " + invoice_number
            if opt[0] in ["-o"]:
                output_file_name = opt[1]
                print "using outpu file", output_file_name
            if opt[0] in ["-p"]:
                print "no latex output"
                no_latex_output=True
        if len(args)>0:
            print "opts:",opts,"args:",args
            raise Usage("Only one input can be accepted !")
    except Usage, err:
        if err.msg == "Help:":
            retcode=0
        else:
            print >>sys.stderr, "Error:",err.msg
            print >>sys.stderr, "for help use --help"
            retcode=2
        
        print "Prints out all invoices that have corresponding lots."
        print
        print "Usage:"
        print
        print "Invoke with",prog_name,"input."
        print "where input is"
        print "   filename"
        print "or file://filename" 
        print "or mysql://user:password@host/databasename" 
        print
        print "-f             force open = ignore lock"
        print "-h or --help   for this help"
        print "-i             for ipython shell"
        print "-l             list all invoices"
        print "-n number      use invoice number (no. from previous run -l)"
        print "-o name        use name as outputfile. default: data.lco"
        print "-p             pretend (=no) latex output"
        
        return retcode

    # Try to open the given input
    try:
        session = gnucash.Session(input_url,ignore_lock=ignore_lock)
    except Exception as exception:
        print "Problem opening input."
        print exception
        return 2
    
    book = session.book
    root_account = book.get_root_account()
    comm_table = book.get_table()
    EUR = comm_table.lookup("CURRENCY", "EUR")

    invoice_list=get_all_invoices_from_lots(root_account)
    if list_invoices:
        for number,invoice in enumerate(invoice_list):
            print "("+str(number)+")"
            print invoice

    if not (no_latex_output):

        if invoice_number == None:
            print "Using the first invoice:"
            invoice_number=0

        invoice=invoice_list[int(invoice_number)]
        print "Using the following invoice:"
        print invoice
    
        lco_str=invoice_to_lco(invoice)

        # Opening output file
        f=open(output_file_name,"w")
        lco_str=lco_str.encode("utf8")
        f.write(lco_str)
        f.close()
        owner = invoice.GetOwner().GetName()
        subprocess.call('pdflatex -jobname "Rekening {} {}" {}'.format(invoice_number, owner, latex_filename), shell = True)

    if with_ipshell:
        ipshell= IPShellEmbed()
        ipshell() 

    #session.save()
    session.end()

if __name__ == "__main__":

    sys.exit(main())

