Summary: wandoujia wdstack agent system
Name: wdstack_agent_v2
Version: 0.0.18
Release: 1
License: GPL 2 license
Group: System Environment/Daemons
URL: http://www.nosa.me
Distribution: Linux
Packager: liningning <liningning@nosa.me>

Requires: python-redis
Requires: supervisor


%description
This is the wandoujia wdstack agent system


%prep
cp -rf $RPM_SOURCE_DIR/wdstack_v2/vmagent .
rm -f vmagent/conf/wdstack_agent_v2.spec 
/bin/rm -rf /home/op/wdstack_agent_v2/*


%build


%install
rm -rf %{buildroot}/*
mkdir -p %{buildroot}
mkdir -p %{buildroot}/home/op/wdstack_agent_v2
cp -rf   vmagent/* %{buildroot}/home/op/wdstack_agent_v2


%post
[ ! -d /etc/supervisor/conf.d ] &&mkdir -p /etc/supervisor/conf.d
/bin/cp -f /home/op/wdstack_agent_v2/conf/wdstack_agent_v2.conf /etc/supervisor/conf.d/

[ ! -d /home/op/wdstack_agent_v2/logs ] &&mkdir -p /home/op/wdstack_agent_v2/logs

supervisorctl reload wdstack_agent_v2 ||{ /etc/init.d/supervisord restart ; }


%preun


%files
/home/op/wdstack_agent_v2
